# =============================================================================
# CÔNG CỤ TẢI TRUYỆN CHỮ TỰ ĐỘNG - Novel Chapter Downloader
# =============================================================================
# Cài đặt thư viện trước khi chạy:
#   pip install selenium beautifulsoup4
# =============================================================================
# Chạy script:
#   python main.py
# =============================================================================

import os
import sys
import time
import random
import re
import json
from typing import Optional, Tuple, Dict

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from bs4 import BeautifulSoup
except ImportError:
    print("\033[91m[!] Thiếu thư viện. Hãy chạy lệnh sau để cài đặt:\033[0m")
    print("\033[93m    pip install selenium beautifulsoup4\033[0m")
    sys.exit(1)

from sources.base import Color, BaseSourceParser
from sources.registry import SOURCES, get_source

# =============================================================================
# HẰNG SỐ VÀ CẤU HÌNH MẶC ĐỊNH
# =============================================================================

DEFAULT_BASE_URL: str = "https://www.69shuba.com/txt"
DEFAULT_OUTPUT_DIR: str = "./truyen_tai_ve"
CONFIG_FILE: str = "config.json"
MAX_CONSECUTIVE_FAILURES: int = 10  # Circuit breaker: dừng sau 10 lỗi liên tiếp

# =============================================================================
# HÀM QUẢN LÝ CẤU HÌNH (CONFIG)
# =============================================================================

def load_config() -> Optional[Dict[str, str]]:
    """Đọc file config.json (nếu tồn tại) để lấy cấu hình lần chạy trước.
    Tự động migrate bổ sung field 'source' nếu thiếu.

    Returns:
        Dict chứa cấu hình hoặc None nếu không có file config.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if isinstance(config, dict):
                    # Migration: nếu thiếu key 'source', tự động điền '69shuba'
                    if "source" not in config:
                        config["source"] = "69shuba"
                        # Ghi lại config đã migrate vào file để đồng bộ
                        save_config(
                            config.get("base_url", DEFAULT_BASE_URL),
                            config.get("output_dir", DEFAULT_OUTPUT_DIR),
                            "69shuba"
                        )
                    return config
        except (json.JSONDecodeError, IOError):
            return None
    return None


def save_config(base_url: str, output_dir: str, source: str) -> None:
    """Lưu cấu hình Base URL, Thư mục lưu file và Nguồn truyện vào config.json
    để tái sử dụng ở lần chạy sau.

    Args:
        base_url: URL gốc của website truyện.
        output_dir: Đường dẫn thư mục lưu file.
        source: Tên nguồn truyện (ví dụ: '69shuba').
    """
    config = {
        "base_url": base_url,
        "output_dir": output_dir,
        "source": source,
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"{Color.YELLOW}[!] Không thể lưu config: {e}{Color.RESET}")


# =============================================================================
# HÀM NHẬP LIỆU TỪ NGƯỜI DÙNG (CLI INPUT)
# =============================================================================

def get_user_input() -> Tuple[str, int, int, int, str, str]:
    """Hỏi người dùng nhập các thông tin cấu hình qua terminal.
    Nếu người dùng bấm Enter bỏ trống, sẽ dùng giá trị mặc định.
    Nếu có config từ lần trước, hỏi người dùng có muốn tái sử dụng không.

    Returns:
        Tuple gồm (base_url, story_id, start_chapter_id, num_chapters, output_dir, source).
    """
    print(f"\n{Color.CYAN}{Color.BOLD}{'═' * 60}{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}   📖  CÔNG CỤ TẢI TRUYỆN CHỮ TỰ ĐỘNG  📖{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}{'═' * 60}{Color.RESET}\n")

    # --- Kiểm tra config lần trước ---
    config = load_config()
    base_url = DEFAULT_BASE_URL
    output_dir = DEFAULT_OUTPUT_DIR
    source = "69shuba"

    if config:
        prev_base_url = config.get("base_url", DEFAULT_BASE_URL)
        prev_output_dir = config.get("output_dir", DEFAULT_OUTPUT_DIR)
        prev_source = config.get("source", "69shuba")

        print(f"{Color.BLUE}[i] Phát hiện cấu hình lần chạy trước:{Color.RESET}")
        print(f"    Nguồn     : {Color.CYAN}{prev_source}{Color.RESET}")
        print(f"    Base URL  : {Color.CYAN}{prev_base_url}{Color.RESET}")
        print(f"    Thư mục   : {Color.CYAN}{prev_output_dir}{Color.RESET}")

        reuse = input(
            f"\n{Color.YELLOW}[?] Dùng lại cấu hình trên? (Y/n): {Color.RESET}"
        ).strip().lower()
        if reuse in ("", "y", "yes"):
            base_url = prev_base_url
            output_dir = prev_output_dir
            source = prev_source
            print(f"{Color.GREEN}[✓] Đã tải lại cấu hình.{Color.RESET}\n")
        else:
            print(f"{Color.DIM}[i] Bỏ qua cấu hình cũ. Nhập cấu hình mới:{Color.RESET}\n")
            config = None

    # --- Nhập Nguồn truyện (nếu chưa dùng config cũ) ---
    if not config:
        supported_list = ", ".join(SOURCES.keys())
        while True:
            user_source = input(
                f"{Color.YELLOW}[?] Chọn nguồn truyện "
                f"{Color.DIM}(hỗ trợ: {supported_list}, mặc định: 69shuba){Color.RESET}: "
            ).strip().lower()
            if not user_source:
                source = "69shuba"
                break
            if user_source in SOURCES:
                source = user_source
                break
            print(f"{Color.RED}[!] Nguồn truyện không hợp lệ. Hãy chọn trong số: {supported_list}{Color.RESET}")

        # --- Nhập Base URL (nếu chưa dùng config cũ) ---
        user_base_url = input(
            f"{Color.YELLOW}[?] Base URL "
            f"{Color.DIM}(mặc định: {DEFAULT_BASE_URL}){Color.RESET}: "
        ).strip()
        if user_base_url:
            base_url = user_base_url.rstrip("/")

    # --- Nhập ID Truyện (bắt buộc) ---
    while True:
        story_id_str = input(
            f"{Color.YELLOW}[?] ID Truyện "
            f"{Color.DIM}(ví dụ: 90438){Color.RESET}: "
        ).strip()
        if story_id_str.isdigit() and int(story_id_str) > 0:
            story_id = int(story_id_str)
            break
        print(f"{Color.RED}[!] ID Truyện phải là số nguyên dương.{Color.RESET}")

    # --- Nhập ID Chương bắt đầu (bắt buộc) ---
    while True:
        chapter_id_str = input(
            f"{Color.YELLOW}[?] ID Chương bắt đầu "
            f"{Color.DIM}(ví dụ: 40755198){Color.RESET}: "
        ).strip()
        if chapter_id_str.isdigit() and int(chapter_id_str) > 0:
            start_chapter_id = int(chapter_id_str)
            break
        print(f"{Color.RED}[!] ID Chương phải là số nguyên dương.{Color.RESET}")

    # --- Nhập số lượng chương ---
    while True:
        num_chapters_str = input(
            f"{Color.YELLOW}[?] Số lượng chương cần tải "
            f"{Color.DIM}(mặc định: 50){Color.RESET}: "
        ).strip()
        if num_chapters_str == "":
            num_chapters = 50
            break
        if num_chapters_str.isdigit() and int(num_chapters_str) > 0:
            num_chapters = int(num_chapters_str)
            break
        print(f"{Color.RED}[!] Số lượng chương phải là số nguyên dương.{Color.RESET}")

    # --- Nhập thư mục lưu file (nếu chưa dùng config cũ) ---
    if not config:
        user_output_dir = input(
            f"{Color.YELLOW}[?] Thư mục lưu file "
            f"{Color.DIM}(mặc định: {DEFAULT_OUTPUT_DIR}){Color.RESET}: "
        ).strip()
        if user_output_dir:
            output_dir = user_output_dir

    # --- Lưu config cho lần chạy sau ---
    save_config(base_url, output_dir, source)

    # --- Hiển thị tóm tắt ---
    print(f"\n{Color.CYAN}{'─' * 60}{Color.RESET}")
    print(f"{Color.BOLD}   📋  TÓM TẮT CẤU HÌNH:{Color.RESET}")
    print(f"   Nguồn truyện    : {Color.GREEN}{source}{Color.RESET}")
    print(f"   Base URL        : {Color.GREEN}{base_url}{Color.RESET}")
    print(f"   ID Truyện       : {Color.GREEN}{story_id}{Color.RESET}")
    print(f"   Chương bắt đầu  : {Color.GREEN}{start_chapter_id}{Color.RESET}")
    print(f"   Số chương tải   : {Color.GREEN}{num_chapters}{Color.RESET}")
    print(f"   Thư mục lưu     : {Color.GREEN}{output_dir}{Color.RESET}")
    print(f"{Color.CYAN}{'─' * 60}{Color.RESET}\n")

    return base_url, story_id, start_chapter_id, num_chapters, output_dir, source


# =============================================================================
# QUẢN LÝ TRÌNH DUYỆT (BROWSER MANAGER)
# =============================================================================

def create_browser() -> webdriver.Chrome:
    """Khởi tạo Chrome browser với cấu hình chống phát hiện automation.
    Cửa sổ được đẩy ra ngoài màn hình để không ảnh hưởng người dùng.

    Returns:
        Instance webdriver.Chrome đã sẵn sàng dùng.
    """
    options = Options()

    # KHÔNG dùng headless - Cloudflare phát hiện headless Chrome
    # Thay vào đó, đẩy cửa sổ ra ngoài màn hình
    options.add_argument('--window-position=-2400,0')
    options.add_argument('--window-size=1920,1080')

    # Chống phát hiện automation
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')

    # Giả lập User-Agent Chrome/Windows thật
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    )

    # Xóa các dấu hiệu Selenium
    options.add_experimental_option(
        'excludeSwitches', ['enable-automation', 'enable-logging']
    )
    options.add_experimental_option('useAutomationExtension', False)

    print(f"{Color.BLUE}[i] Đang khởi tạo trình duyệt Chrome...{Color.RESET}")

    try:
        driver = webdriver.Chrome(options=options)

        # Inject JavaScript để xóa navigator.webdriver và thêm các property
        # mà trình duyệt thật có (Chrome runtime, plugins, languages)
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en']
                });
            '''
        })

        print(f"{Color.GREEN}[✓] Trình duyệt đã sẵn sàng.{Color.RESET}")
        return driver

    except Exception as e:
        print(f"{Color.RED}[✗] Không thể khởi tạo Chrome: {e}{Color.RESET}")
        print(f"{Color.YELLOW}[!] Đảm bảo đã cài Google Chrome trên máy.{Color.RESET}")
        print(f"{Color.YELLOW}[!] Selenium sẽ tự tải ChromeDriver phù hợp.{Color.RESET}")
        sys.exit(1)


# =============================================================================
# HÀM XỬ LÝ FILE HỆ THỐNG (FILE I/O)
# =============================================================================

def sanitize_filename(name: str) -> str:
    """Dọn dẹp tên file/folder: loại bỏ ký tự không hợp lệ trên
    Windows/Linux (\ / : * ? " < > |).

    Args:
        name: Tên gốc cần sanitize.

    Returns:
        Tên đã được làm sạch, an toàn cho hệ thống file.
    """
    # Loại bỏ ký tự không hợp lệ trên Windows/Linux
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', name)

    # Loại bỏ ký tự điều khiển (control characters)
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)

    # Gộp nhiều dấu gạch dưới liên tiếp
    sanitized = re.sub(r'_+', '_', sanitized)

    # Xóa khoảng trắng thừa và dấu chấm cuối (Windows issue)
    sanitized = sanitized.strip().rstrip('.')

    # Giới hạn độ dài (Windows max = 255 chars)
    if len(sanitized) > 200:
        sanitized = sanitized[:200]

    if not sanitized:
        sanitized = "untitled"

    return sanitized


def save_to_markdown(
    output_dir: str,
    story_name: str,
    chapter_name: str,
    content: str,
    chapter_index: int
) -> str:
    """Lưu nội dung chương thành file Markdown (.md).

    Format file:
        # {Tên Chương gốc}
        (dòng trống)
        Nội dung text...

    Args:
        output_dir: Thư mục gốc lưu file.
        story_name: Tên truyện → tên thư mục con.
        chapter_name: Tên chương → tên file.
        content: Nội dung đã làm sạch.
        chapter_index: Số thứ tự chương (prefix trong tên file).

    Returns:
        Đường dẫn đầy đủ tới file .md đã lưu.
    """
    safe_story_name = sanitize_filename(story_name)
    safe_chapter_name = sanitize_filename(chapter_name)

    # Prefix số thứ tự để sắp xếp đúng (0001_, 0002_, ...)
    filename = f"{chapter_index:04d}_{safe_chapter_name}.md"

    # Tạo thư mục: {output_dir}/{tên_truyện}/
    story_dir = os.path.join(output_dir, safe_story_name)
    os.makedirs(story_dir, exist_ok=True)

    # Format Markdown: heading + nội dung
    md_content = f"# {chapter_name}\n\n{content}\n"

    filepath = os.path.join(story_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    return filepath


# =============================================================================
# HÀM CHÍNH - VÒNG LẶP TẢI CHƯƠNG (MAIN LOOP)
# =============================================================================

def download_chapters(
    base_url: str,
    story_id: int,
    start_chapter_id: int,
    num_chapters: int,
    output_dir: str,
    parser: BaseSourceParser
) -> None:
    """Vòng lặp chính: tải từng chương, parse, và lưu file.
    Tự động xử lý ID gap và có cơ chế circuit breaker.

    Args:
        base_url: URL gốc.
        story_id: ID truyện.
        start_chapter_id: ID chương bắt đầu.
        num_chapters: Số chương cần tải thành công.
        output_dir: Thư mục lưu.
        parser: Parser strategy xử lý cào/bóc tách cho nguồn truyện.
    """
    successful_downloads: int = 0
    consecutive_failures: int = 0
    current_chapter_id: int = start_chapter_id
    story_name: Optional[str] = None
    total_attempted: int = 0

    # --- Khởi tạo browser ---
    driver = create_browser()

    print(f"\n{Color.GREEN}{Color.BOLD}[▶] Bắt đầu tải truyện...{Color.RESET}\n")

    try:
        while successful_downloads < num_chapters:
            # --- URL qua parser ---
            url = parser.build_chapter_url(story_id, current_chapter_id)
            total_attempted += 1
            is_first = (total_attempted == 1)

            print(
                f"{Color.BLUE}[→] Đang tải ID {current_chapter_id}..."
                f"{Color.RESET}",
                end=" ",
                flush=True
            )

            # --- Tải HTML qua parser ---
            html = parser.get_html(driver, url, is_first_request=is_first)

            # --- Thất bại: chương không tồn tại ---
            if html is None:
                consecutive_failures += 1
                print(
                    f"{Color.YELLOW}[⚠] Chương ID [{current_chapter_id}] "
                    f"không tồn tại, đang thử ID tiếp theo... "
                    f"({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})"
                    f"{Color.RESET}"
                )

                # CIRCUIT BREAKER
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print(
                        f"\n{Color.RED}{Color.BOLD}[✗] CIRCUIT BREAKER: "
                        f"{MAX_CONSECUTIVE_FAILURES} lỗi liên tiếp!"
                        f"{Color.RESET}"
                    )
                    print(
                        f"{Color.RED}    Có thể đã đến chương mới nhất "
                        f"hoặc website đổi URL.{Color.RESET}"
                    )
                    break

                current_chapter_id += 1
                time.sleep(random.uniform(0.5, 1.5))
                continue

            # --- Parse HTML qua parser ---
            result = parser.parse_chapter(html)

            if result is None:
                consecutive_failures += 1
                print(
                    f"{Color.YELLOW}[⚠] Chương ID [{current_chapter_id}] "
                    f"nội dung rỗng, thử tiếp... "
                    f"({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})"
                    f"{Color.RESET}"
                )

                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print(
                        f"\n{Color.RED}{Color.BOLD}[✗] CIRCUIT BREAKER: "
                        f"{MAX_CONSECUTIVE_FAILURES} lỗi liên tiếp!"
                        f"{Color.RESET}"
                    )
                    print(
                        f"{Color.RED}    Kiểm tra CSS Selector trong "
                        f"parse_chapter().{Color.RESET}"
                    )
                    break

                current_chapter_id += 1
                time.sleep(random.uniform(0.5, 1.5))
                continue

            # --- THÀNH CÔNG! ---
            consecutive_failures = 0
            successful_downloads += 1

            parsed_story_name, chapter_name, content = result

            if story_name is None:
                story_name = parsed_story_name
                print(
                    f"\n{Color.MAGENTA}[i] Tên truyện: "
                    f"{Color.BOLD}{story_name}{Color.RESET}\n"
                )

            # --- Lưu file ---
            filepath = save_to_markdown(
                output_dir, story_name, chapter_name,
                content, successful_downloads
            )

            print(
                f"{Color.GREEN}[✓] Chương "
                f"{successful_downloads}/{num_chapters}: "
                f"{Color.BOLD}{chapter_name}{Color.RESET} "
                f"{Color.DIM}→ {filepath}{Color.RESET}"
            )

            # --- ID tiếp theo ---
            current_chapter_id += 1

            # --- Anti-ban: sleep 1.0 - 2.5 giây ---
            if successful_downloads < num_chapters:
                delay = random.uniform(1.0, 2.5)
                print(f"{Color.DIM}    ⏳ Chờ {delay:.1f}s...{Color.RESET}")
                time.sleep(delay)

    finally:
        # --- Luôn đóng browser ---
        try:
            driver.quit()
            print(f"\n{Color.DIM}[i] Đã đóng trình duyệt.{Color.RESET}")
        except Exception:
            pass

    # =================================================================
    # BÁO CÁO KẾT QUẢ
    # =================================================================
    print(f"\n{Color.CYAN}{'═' * 60}{Color.RESET}")
    print(f"{Color.BOLD}   📊  BÁO CÁO KẾT QUẢ:{Color.RESET}")
    print(f"   Tổng ID đã thử      : {Color.CYAN}{total_attempted}{Color.RESET}")
    print(
        f"   Chương tải thành công: "
        f"{Color.GREEN}{successful_downloads}/{num_chapters}{Color.RESET}"
    )
    if story_name:
        safe_name = sanitize_filename(story_name)
        full_path = os.path.abspath(os.path.join(output_dir, safe_name))
        print(f"   Thư mục lưu trữ     : {Color.GREEN}{full_path}{Color.RESET}")
    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
        print(
            f"   Trạng thái           : "
            f"{Color.RED}Dừng do Circuit Breaker{Color.RESET}"
        )
    elif successful_downloads == num_chapters:
        print(
            f"   Trạng thái           : "
            f"{Color.GREEN}Hoàn tất ✓{Color.RESET}"
        )
    print(f"{Color.CYAN}{'═' * 60}{Color.RESET}\n")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main() -> None:
    """Điểm khởi chạy chương trình."""
    try:
        base_url, story_id, start_chapter_id, num_chapters, output_dir, source = (
            get_user_input()
        )

        confirm = input(
            f"{Color.YELLOW}[?] Bắt đầu tải {num_chapters} chương? (Y/n): "
            f"{Color.RESET}"
        ).strip().lower()

        if confirm in ("n", "no"):
            print(f"{Color.DIM}[i] Đã hủy.{Color.RESET}")
            return

        # Khởi tạo parser tương ứng từ registry
        parser = get_source(source, base_url)

        download_chapters(
            base_url, story_id, start_chapter_id, num_chapters, output_dir, parser
        )

    except KeyboardInterrupt:
        print(
            f"\n\n{Color.YELLOW}[!] Đã dừng (Ctrl+C). "
            f"Các chương đã tải vẫn an toàn.{Color.RESET}\n"
        )
        sys.exit(0)
    except Exception as e:
        print(f"\n{Color.RED}[✗] Lỗi: {e}{Color.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
