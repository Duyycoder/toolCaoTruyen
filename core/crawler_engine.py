import os
import sys
import time
import random
import re
from typing import Optional, Tuple, Callable, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from sources.base import Color, BaseSourceParser

MAX_CONSECUTIVE_FAILURES: int = 10  # Circuit breaker: dừng sau 10 lỗi liên tiếp

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


def default_progress_callback(event_data: dict) -> None:
    """Callback mặc định in tiến độ ra console cho giao diện CLI (main.py)."""
    event = event_data.get("event")
    if event == "start":
        print(f"\n{Color.GREEN}{Color.BOLD}[▶] Bắt đầu tải truyện...{Color.RESET}\n")
    elif event == "before_download":
        chapter_id = event_data.get("chapter_id")
        print(f"{Color.BLUE}[→] Đang tải ID {chapter_id}...{Color.RESET}", end=" ", flush=True)
    elif event == "chapter_not_exist":
        chapter_id = event_data.get("chapter_id")
        consecutive_failures = event_data.get("consecutive_failures")
        max_failures = event_data.get("max_failures")
        print(
            f"{Color.YELLOW}[⚠] Chương ID [{chapter_id}] "
            f"không tồn tại, đang thử ID tiếp theo... "
            f"({consecutive_failures}/{max_failures})"
            f"{Color.RESET}"
        )
    elif event == "chapter_empty":
        chapter_id = event_data.get("chapter_id")
        consecutive_failures = event_data.get("consecutive_failures")
        max_failures = event_data.get("max_failures")
        print(
            f"{Color.YELLOW}[⚠] Chương ID [{chapter_id}] "
            f"nội dung rỗng, thử tiếp... "
            f"({consecutive_failures}/{max_failures})"
            f"{Color.RESET}"
        )
    elif event == "circuit_breaker":
        max_failures = event_data.get("max_failures")
        reason = event_data.get("reason", "")
        print(
            f"\n{Color.RED}{Color.BOLD}[✗] CIRCUIT BREAKER: "
            f"{max_failures} lỗi liên tiếp!"
            f"{Color.RESET}"
        )
        if reason == "empty":
            print(
                f"{Color.RED}    Kiểm tra CSS Selector trong "
                f"parse_chapter().{Color.RESET}"
            )
        else:
            print(
                f"{Color.RED}    Có thể đã đến chương mới nhất "
                f"hoặc website đổi URL.{Color.RESET}"
            )
    elif event == "story_name":
        story_name = event_data.get("story_name")
        print(
            f"\n{Color.MAGENTA}[i] Tên truyện: "
            f"{Color.BOLD}{story_name}{Color.RESET}\n"
        )
    elif event == "chapter_success":
        successful_downloads = event_data.get("successful_downloads")
        num_chapters = event_data.get("num_chapters")
        chapter_name = event_data.get("chapter_name")
        filepath = event_data.get("filepath")
        print(
            f"{Color.GREEN}[✓] Chương "
            f"{successful_downloads}/{num_chapters}: "
            f"{Color.BOLD}{chapter_name}{Color.RESET} "
            f"{Color.DIM}→ {filepath}{Color.RESET}"
        )
    elif event == "delay":
        delay = event_data.get("delay")
        print(f"{Color.DIM}    ⏳ Chờ {delay:.1f}s...{Color.RESET}")
    elif event == "stopped":
        print(f"\n{Color.YELLOW}[!] Quá trình tải đã bị người dùng dừng lại.{Color.RESET}\n")
    elif event == "complete":
        total_attempted = event_data.get("total_attempted")
        successful_downloads = event_data.get("successful_downloads")
        num_chapters = event_data.get("num_chapters")
        story_name = event_data.get("story_name")
        output_dir = event_data.get("output_dir")
        consecutive_failures = event_data.get("consecutive_failures")
        max_failures = event_data.get("max_failures")
        
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
        if consecutive_failures >= max_failures:
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


def extract_chapter_id_from_url(url: str, fallback_id: int) -> int:
    """Trích xuất ID chương từ URL chương truyện phục vụ cho callback hiển thị.
    KHÔNG được dùng trong bất kỳ điều kiện if/while nào quyết định luồng chạy.
    """
    try:
        match = re.search(r"/txt/\d+/(\d+)", url)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return fallback_id


def download_chapters(
    base_url: str,
    story_id: int,
    start_chapter_id: int,
    num_chapters: int,
    output_dir: str,
    parser: BaseSourceParser,
    progress_callback: Optional[Callable[[dict], None]] = None,
    is_stopped: Optional[Callable[[], bool]] = None
) -> None:
    """Vòng lặp chính: tải từng chương, parse, và lưu file.
    Điều hướng theo liên kết thật (next-chapter url) thay vì tự tăng ID + 1.
    Thông báo tiến độ qua progress_callback để hỗ trợ Web UI.

    Args:
        base_url: URL gốc.
        story_id: ID truyện.
        start_chapter_id: ID chương bắt đầu.
        num_chapters: Số chương cần tải thành công.
        output_dir: Thư mục lưu.
        parser: Parser strategy xử lý cào/bóc tách cho nguồn truyện.
        progress_callback: Callback nhận dữ liệu JSON mô tả sự kiện tiến triển.
        is_stopped: Hàm kiểm tra xem quá trình tải có bị dừng hay không.
    """
    if progress_callback is None:
        progress_callback = default_progress_callback

    successful_downloads: int = 0
    consecutive_failures: int = 0
    story_name: Optional[str] = None
    total_attempted: int = 0
    reached_end: bool = False

    # Khởi tạo URL chương đầu tiên từ ID người dùng nhập
    current_url: str = parser.build_chapter_url(story_id, start_chapter_id)
    
    # Tập hợp các URL đã tải trong phiên này để chống lặp vô hạn
    visited_urls = set()

    # --- Khởi tạo browser ---
    driver = create_browser()

    progress_callback({"event": "start", "message": "Bắt đầu tải truyện..."})

    try:
        while successful_downloads < num_chapters:
            # --- Kiểm tra dừng giữa các lần lặp ---
            if is_stopped and is_stopped():
                progress_callback({
                    "event": "stopped",
                    "message": "Quá trình tải đã bị dừng bởi người dùng."
                })
                break

            # Kiểm tra chống lặp vô hạn
            if current_url in visited_urls:
                progress_callback({
                    "event": "error",
                    "message": f"[✗] Lỗi vòng lặp vô hạn: Phát hiện URL đã tải trước đó trong phiên này ({current_url})."
                })
                break

            # Trích xuất ID chỉ để phục vụ callback hiển thị
            current_chapter_id = extract_chapter_id_from_url(current_url, start_chapter_id)

            # --- Vòng lặp thử lại cùng một URL (tối đa 3 lần) ---
            page_load_retry_count = 0
            load_success = False
            html = None
            result = None

            while page_load_retry_count < 3:
                total_attempted += 1
                is_first = (total_attempted == 1)

                retry_suffix = f" (thử lại {page_load_retry_count}/2)" if page_load_retry_count > 0 else ""
                progress_callback({
                    "event": "before_download",
                    "chapter_id": current_chapter_id,
                    "message": f"Đang tải ID {current_chapter_id}{retry_suffix}..."
                })

                # Tải HTML
                html = parser.get_html(driver, current_url, is_first_request=is_first)

                # Nếu tải HTML thành công, tiến hành parse
                if html is not None:
                    result = parser.parse_chapter(html)
                    if result is not None:
                        load_success = True
                        break

                page_load_retry_count += 1

                # Gửi thông báo lỗi tạm thời qua callback
                if html is None:
                    progress_callback({
                        "event": "chapter_not_exist",
                        "chapter_id": current_chapter_id,
                        "consecutive_failures": page_load_retry_count,
                        "max_failures": 3,
                        "message": f"Chương không tồn tại hoặc lỗi mạng (thử lại {page_load_retry_count}/3)."
                    })
                else:
                    progress_callback({
                        "event": "chapter_empty",
                        "chapter_id": current_chapter_id,
                        "consecutive_failures": page_load_retry_count,
                        "max_failures": 3,
                        "message": f"Nội dung chương rỗng (thử lại {page_load_retry_count}/3)."
                    })

                time.sleep(random.uniform(0.5, 1.5))

            # --- Xử lý khi thất bại hoàn toàn 3 lần trên cùng 1 URL ---
            if not load_success:
                consecutive_failures += 1
                progress_callback({
                    "event": "error",
                    "message": f"[✗] Không thể tải chương ID {current_chapter_id} sau 3 lần thử."
                })

                # CIRCUIT BREAKER TỔNG
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    progress_callback({
                        "event": "circuit_breaker",
                        "max_failures": MAX_CONSECUTIVE_FAILURES,
                        "reason": "load_error",
                        "message": f"Circuit breaker kích hoạt do {MAX_CONSECUTIVE_FAILURES} lỗi chương liên tiếp."
                    })
                # Do không thể lấy được URL tiếp theo nếu trang hiện tại lỗi, ta bắt buộc phải dừng vòng lặp tải
                break

            # --- THÀNH CÔNG! Reset các bộ đếm ngay lập tức ---
            consecutive_failures = 0
            visited_urls.add(current_url)
            successful_downloads += 1

            parsed_story_name, chapter_name, content = result

            if story_name is None:
                story_name = parsed_story_name
                progress_callback({
                    "event": "story_name",
                    "story_name": story_name,
                    "message": f"Tên truyện: {story_name}"
                })

            # --- Lưu file ---
            filepath = save_to_markdown(
                output_dir, story_name, chapter_name,
                content, successful_downloads
            )

            progress_callback({
                "event": "chapter_success",
                "successful_downloads": successful_downloads,
                "num_chapters": num_chapters,
                "chapter_name": chapter_name,
                "filepath": filepath,
                "message": f"Chương {successful_downloads}/{num_chapters}: {chapter_name}"
            })

            # --- Xác định URL chương tiếp theo từ DOM thực ---
            next_url = parser.get_next_chapter_url(driver)

            if next_url is None:
                # Đã đến chương cuối cùng của truyện
                reached_end = True
                break

            current_url = next_url

            # --- Anti-ban: sleep 1.0 - 2.5 giây ---
            if successful_downloads < num_chapters:
                if is_stopped and is_stopped():
                    progress_callback({
                        "event": "stopped",
                        "message": "Quá trình tải đã bị dừng bởi người dùng."
                    })
                    break
                delay = random.uniform(1.0, 2.5)
                progress_callback({
                    "event": "delay",
                    "delay": delay,
                    "message": f"⏳ Chờ {delay:.1f}s..."
                })
                time.sleep(delay)

    finally:
        # --- Luôn đóng browser ---
        try:
            driver.quit()
            print(f"\n{Color.DIM}[i] Đã đóng trình duyệt.{Color.RESET}")
        except Exception:
            pass

    progress_callback({
        "event": "complete",
        "total_attempted": total_attempted,
        "successful_downloads": successful_downloads,
        "num_chapters": num_chapters,
        "story_name": story_name,
        "output_dir": output_dir,
        "consecutive_failures": consecutive_failures,
        "max_failures": MAX_CONSECUTIVE_FAILURES,
        "reached_end": reached_end,
        "message": "Đã tải đến chương cuối của truyện." if reached_end else "Hoàn tất quá trình tải."
    })

