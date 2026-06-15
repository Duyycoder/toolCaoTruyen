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


# =============================================================================
# HẰNG SỐ VÀ CẤU HÌNH MẶC ĐỊNH
# =============================================================================

DEFAULT_BASE_URL: str = "https://www.69shuba.com/txt"
DEFAULT_OUTPUT_DIR: str = "./truyen_tai_ve"
CONFIG_FILE: str = "config.json"
MAX_CONSECUTIVE_FAILURES: int = 10  # Circuit breaker: dừng sau 10 lỗi liên tiếp

# Các chuỗi rác/quảng cáo thường xuất hiện trên 69shuba, cần loại bỏ
# (Cập nhật thêm nếu website thay đổi nội dung quảng cáo)
AD_PATTERNS: list[str] = [
    r"69shuba\.com",
    r"69书吧",
    r"六九书吧",
    r"请记住本站域名",
    r"手机版阅读网址",
    r"本站域名",
    r"最新网址",
    r"百度搜索",
    r"www\.69shu\.com",
    r"69shu\.com",
    r"m\.69shu\.com",
    r"请收藏本站",
    r"推荐.*阅读",
    r"加入书签",
    r"笔趣阁",
    r"loadAdv",
]


# =============================================================================
# MÃ MÀU TERMINAL (ANSI Escape Codes)
# =============================================================================

class Color:
    """Mã màu ANSI cho output terminal."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


# =============================================================================
# HÀM QUẢN LÝ CẤU HÌNH (CONFIG)
# =============================================================================

def load_config() -> Optional[Dict[str, str]]:
    """Đọc file config.json (nếu tồn tại) để lấy cấu hình lần chạy trước.

    Returns:
        Dict chứa cấu hình hoặc None nếu không có file config.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    return None


def save_config(base_url: str, output_dir: str) -> None:
    """Lưu cấu hình Base URL và Thư mục lưu file vào config.json
    để tái sử dụng ở lần chạy sau.

    Args:
        base_url: URL gốc của website truyện.
        output_dir: Đường dẫn thư mục lưu file.
    """
    config = {
        "base_url": base_url,
        "output_dir": output_dir,
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"{Color.YELLOW}[!] Không thể lưu config: {e}{Color.RESET}")


# =============================================================================
# HÀM NHẬP LIỆU TỪ NGƯỜI DÙNG (CLI INPUT)
# =============================================================================

def get_user_input() -> Tuple[str, int, int, int, str]:
    """Hỏi người dùng nhập các thông tin cấu hình qua terminal.
    Nếu người dùng bấm Enter bỏ trống, sẽ dùng giá trị mặc định.
    Nếu có config từ lần trước, hỏi người dùng có muốn tái sử dụng không.

    Returns:
        Tuple gồm (base_url, story_id, start_chapter_id, num_chapters, output_dir).
    """
    print(f"\n{Color.CYAN}{Color.BOLD}{'═' * 60}{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}   📖  CÔNG CỤ TẢI TRUYỆN CHỮ TỰ ĐỘNG  📖{Color.RESET}")
    print(f"{Color.CYAN}{Color.BOLD}{'═' * 60}{Color.RESET}\n")

    # --- Kiểm tra config lần trước ---
    config = load_config()
    base_url = DEFAULT_BASE_URL
    output_dir = DEFAULT_OUTPUT_DIR

    if config:
        prev_base_url = config.get("base_url", DEFAULT_BASE_URL)
        prev_output_dir = config.get("output_dir", DEFAULT_OUTPUT_DIR)

        print(f"{Color.BLUE}[i] Phát hiện cấu hình lần chạy trước:{Color.RESET}")
        print(f"    Base URL  : {Color.CYAN}{prev_base_url}{Color.RESET}")
        print(f"    Thư mục   : {Color.CYAN}{prev_output_dir}{Color.RESET}")

        reuse = input(
            f"\n{Color.YELLOW}[?] Dùng lại cấu hình trên? (Y/n): {Color.RESET}"
        ).strip().lower()
        if reuse in ("", "y", "yes"):
            base_url = prev_base_url
            output_dir = prev_output_dir
            print(f"{Color.GREEN}[✓] Đã tải lại cấu hình.{Color.RESET}\n")
        else:
            print(f"{Color.DIM}[i] Bỏ qua cấu hình cũ. Nhập cấu hình mới:{Color.RESET}\n")
            config = None

    # --- Nhập Base URL (nếu chưa dùng config cũ) ---
    if not config:
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
    save_config(base_url, output_dir)

    # --- Hiển thị tóm tắt ---
    print(f"\n{Color.CYAN}{'─' * 60}{Color.RESET}")
    print(f"{Color.BOLD}   📋  TÓM TẮT CẤU HÌNH:{Color.RESET}")
    print(f"   Base URL        : {Color.GREEN}{base_url}{Color.RESET}")
    print(f"   ID Truyện       : {Color.GREEN}{story_id}{Color.RESET}")
    print(f"   Chương bắt đầu  : {Color.GREEN}{start_chapter_id}{Color.RESET}")
    print(f"   Số chương tải   : {Color.GREEN}{num_chapters}{Color.RESET}")
    print(f"   Thư mục lưu     : {Color.GREEN}{output_dir}{Color.RESET}")
    print(f"{Color.CYAN}{'─' * 60}{Color.RESET}\n")

    return base_url, story_id, start_chapter_id, num_chapters, output_dir


# =============================================================================
# QUẢN LÝ TRÌNH DUYỆT (BROWSER MANAGER)
# =============================================================================
# Website 69shuba.com dùng Cloudflare Managed Challenge (JavaScript challenge)
# để chống bot. Các thư viện HTTP thuần (requests, cloudscraper) KHÔNG vượt qua
# được vì Cloudflare yêu cầu thực thi JavaScript trong trình duyệt thật.
#
# Giải pháp: Dùng Selenium với Chrome KHÔNG headless (non-headless).
# - Headless Chrome bị Cloudflare phát hiện qua navigator.webdriver và
#   các fingerprint khác.
# - Non-headless Chrome bypass Cloudflare ngay lập tức.
# - Cửa sổ Chrome được đẩy ra ngoài màn hình (vị trí -2400,0) nên
#   KHÔNG ảnh hưởng trải nghiệm người dùng.
# - Session cookies được giữ nguyên giữa các request, nên chỉ cần
#   vượt CF 1 lần duy nhất.
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


def get_html(
    driver: webdriver.Chrome,
    url: str,
    is_first_request: bool = False
) -> Optional[str]:
    """Dùng Chrome browser để tải HTML của URL.
    Tự động chờ Cloudflare challenge nếu gặp.

    Args:
        driver: Instance webdriver.Chrome đang dùng.
        url: URL đầy đủ của trang cần tải.
        is_first_request: True nếu đây là request đầu tiên (chờ CF lâu hơn).

    Returns:
        Chuỗi HTML nếu thành công, None nếu thất bại.
    """
    try:
        driver.get(url)

        # Chờ Cloudflare challenge tự giải quyết
        # Lần đầu tiên: chờ tối đa 30s (CF cần xác minh trình duyệt)
        # Các lần sau: chờ tối đa 10s (đã có cookies, thường pass ngay)
        max_wait = 30 if is_first_request else 10

        for i in range(max_wait):
            title = driver.title or ""

            # Nếu gặp trang "Just a moment..." → đang chờ CF challenge
            if "Just a moment" in title:
                if i == 0 and is_first_request:
                    print(
                        f"{Color.YELLOW}[⏳] Đang vượt Cloudflare..."
                        f"{Color.RESET}",
                        end=" ",
                        flush=True
                    )
                time.sleep(1)
                continue

            # Title có nội dung thật → challenge đã pass
            if title and "Just a moment" not in title:
                if is_first_request and i > 0:
                    print(f"{Color.GREEN}OK!{Color.RESET}")
                break

            time.sleep(0.5)

        # Kiểm tra sau khi chờ
        final_title = driver.title or ""
        if "Just a moment" in final_title:
            if is_first_request:
                print(f"{Color.RED}Thất bại!{Color.RESET}")
            return None

        html = driver.page_source
        if not html or len(html) < 500:
            return None

        # Kiểm tra trang 404 (chương bị xóa / không tồn tại)
        if "404" in final_title or "找不到" in final_title or "不存在" in final_title:
            return None

        # Kiểm tra có nội dung truyện hay không
        # (div.txtnav hoặc div#txtright là selector chính của 69shuba)
        if "txtnav" not in html and "txtright" not in html:
            return None

        return html

    except Exception as e:
        print(f"{Color.RED}[✗] Lỗi trình duyệt: {e}{Color.RESET}")
        return None


# =============================================================================
# HÀM BÓC TÁCH DỮ LIỆU (PARSING)
# =============================================================================

def parse_chapter(html: str) -> Optional[Tuple[str, str, str]]:
    """Phân tích HTML để trích xuất tên truyện, tên chương và nội dung.
    Sử dụng BeautifulSoup4 với các CSS Selector phù hợp cho 69shuba.com.

    *** GHI CHÚ BẢO TRÌ - CẬP NHẬT CSS SELECTOR ***
    Nếu website 69shuba thay đổi giao diện, cần cập nhật các CSS Selector
    bên dưới. Mỗi selector đều có comment giải thích mục đích.

    Cấu trúc HTML hiện tại (verified 2025-12):
        <div class="txtnav">        ← Container chính
          <h1 class="hide720">      ← Tên chương
          <div class="txtinfo">     ← Thông tin (ngày, tác giả)
          <div id="txtright">       ← NỘI DUNG TRUYỆN
          <div class="txtbottom">   ← Nút navigation
        </div>

    Biến JS bookinfo chứa:
        articlename: tên truyện
        chaptername: tên chương
        next_page / preview_page: URL chương kế/trước

    Args:
        html: Chuỗi HTML của trang chương truyện.

    Returns:
        Tuple (tên_truyện, tên_chương, nội_dung) nếu parse thành công,
        None nếu không tìm thấy nội dung.
    """
    soup = BeautifulSoup(html, "html.parser")

    # ===================================================================
    # PHƯƠNG PHÁP 1: Lấy thông tin từ biến JavaScript bookinfo
    # 69shuba nhúng metadata vào biến JS "bookinfo" trong <script>
    # Đây là nguồn ĐÁG TIN CẬY NHẤT cho tên truyện/chương
    # ===================================================================
    story_name = "Unknown"
    chapter_name = ""

    bookinfo_match = re.search(
        r"var\s+bookinfo\s*=\s*\{(.*?)\};",
        html,
        re.DOTALL
    )
    if bookinfo_match:
        bookinfo_text = bookinfo_match.group(1)

        # Trích xuất articlename (tên truyện gốc tiếng Trung)
        name_match = re.search(r"articlename:\s*'([^']*)'", bookinfo_text)
        if name_match:
            story_name = name_match.group(1).strip()

        # Trích xuất chaptername (tên chương)
        chapter_match = re.search(r"chaptername:\s*'([^']*)'", bookinfo_text)
        if chapter_match:
            chapter_name = chapter_match.group(1).strip()

    # ===================================================================
    # PHƯƠNG PHÁP 2 (Fallback): Lấy tên từ HTML elements
    # Dùng khi biến bookinfo không tồn tại
    # ===================================================================

    # --- Tên truyện fallback: breadcrumb ---
    # CSS Selector: div.bread → chứa các link navigation
    # Cấu trúc: 首页 > Thể loại > [Tên truyện link] > Tên chương (text)
    if story_name == "Unknown":
        breadcrumb = soup.select_one("div.bread")
        if breadcrumb:
            links = breadcrumb.find_all("a")
            if len(links) >= 2:
                story_name = links[-1].get_text(strip=True)
            elif len(links) == 1:
                story_name = links[0].get_text(strip=True)

    # --- Tên truyện fallback: <title> ---
    # Format: "Tên truyện-Tên chương-69书吧"
    if story_name == "Unknown" and soup.title:
        title_text = soup.title.get_text(strip=True)
        parts = title_text.split("-")
        if len(parts) >= 2:
            story_name = parts[0].strip()

    # --- Tên chương fallback: <h1 class="hide720"> ---
    # Heading chính chứa tên chương (ẩn trên mobile ≤720px)
    if not chapter_name:
        h1_tag = soup.select_one("h1.hide720, h1.txtTitle, h1")
        if h1_tag:
            chapter_name = h1_tag.get_text(strip=True)

    # --- Tên chương fallback: <title> ---
    if not chapter_name and soup.title:
        title_text = soup.title.get_text(strip=True)
        parts = title_text.split("-")
        if len(parts) >= 2:
            chapter_name = parts[1].strip()
        elif parts:
            chapter_name = parts[0].strip()

    if not chapter_name:
        return None  # Không tìm thấy tên chương → trang không hợp lệ

    # ===================================================================
    # TRÍCH XUẤT NỘI DUNG CHƯƠNG
    # Ưu tiên: div.txtnav (container chính)
    # Fallback: div#txtright, div.txtcont, div#content
    # ===================================================================
    content_div = None

    content_selectors = [
        "div.txtnav",           # Container nội dung chính 69shuba
        "div#txtright",         # Div con chứa text truyện
        "div.txtcont",          # Variant khác
        "div#content",          # Selector phổ biến nhiều site
        "div.chapter-content",  # Fallback
        "div.content",          # Fallback
    ]

    for selector in content_selectors:
        content_div = soup.select_one(selector)
        if content_div:
            break

    if not content_div:
        return None

    # --- Làm sạch nội dung ---
    content_text = _clean_content(content_div)

    if not content_text or len(content_text.strip()) < 50:
        return None

    return story_name, chapter_name, content_text


def _clean_content(content_div: BeautifulSoup) -> str:
    """Làm sạch nội dung HTML: loại bỏ quảng cáo, chuyển đổi thẻ HTML
    thành format Markdown phù hợp.

    Quy trình:
    1. Xóa thẻ script/style/iframe/ins
    2. Xóa heading (h1) và div phụ trợ (txtinfo, txtbottom, pagebtn)
    3. Chuyển <br> → newline, <p> → đoạn văn Markdown
    4. Loại bỏ dòng chứa text quảng cáo theo regex pattern
    5. Chuẩn hóa khoảng trắng

    Args:
        content_div: Thẻ BeautifulSoup chứa nội dung chương.

    Returns:
        Chuỗi text đã làm sạch, sẵn sàng ghi vào file .md.
    """
    # Bước 1: Loại bỏ thẻ rác (quảng cáo, tracking)
    for tag in content_div.find_all(
        ["script", "style", "iframe", "ins", "noscript"]
    ):
        tag.decompose()

    # Bước 2: Loại bỏ heading và div không phải nội dung truyện
    for tag in content_div.find_all(["h1"]):
        tag.decompose()
    for tag in content_div.find_all("div", class_="txtinfo"):
        tag.decompose()
    for tag in content_div.find_all("div", class_=re.compile(
        r"txtbottom|pagebtn|bookbtn|txtlast|operation"
    )):
        tag.decompose()

    # Bước 3: Chuyển <br>/<br/> thành newline
    for br in content_div.find_all("br"):
        br.replace_with("\n")

    # Bước 4: Chuyển </p><p> thành hai dòng trống (phân đoạn Markdown)
    for p_tag in content_div.find_all("p"):
        p_tag.insert_before("\n\n")
        p_tag.insert_after("\n\n")

    # Bước 5: Lấy toàn bộ text thô
    raw_text = content_div.get_text()

    # Bước 6: Loại bỏ dòng quảng cáo theo regex pattern
    lines = raw_text.split("\n")
    cleaned_lines = []
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            cleaned_lines.append("")
            continue

        # Kiểm tra từng dòng với danh sách pattern quảng cáo
        is_ad = False
        for pattern in AD_PATTERNS:
            if re.search(pattern, line_stripped, re.IGNORECASE):
                is_ad = True
                break
        if not is_ad:
            cleaned_lines.append(line_stripped)

    # Bước 7: Gộp và chuẩn hóa dòng trống (tối đa 2 liên tiếp = 1 đoạn MD)
    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text


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
    output_dir: str
) -> None:
    """Vòng lặp chính: tải từng chương, parse, và lưu file.
    Tự động xử lý ID gap và có cơ chế circuit breaker.

    Args:
        base_url: URL gốc.
        story_id: ID truyện.
        start_chapter_id: ID chương bắt đầu.
        num_chapters: Số chương cần tải thành công.
        output_dir: Thư mục lưu.
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
            # --- URL: {Base_URL}/{ID_Truyen}/{ID_Chuong} ---
            url = f"{base_url}/{story_id}/{current_chapter_id}"
            total_attempted += 1
            is_first = (total_attempted == 1)

            print(
                f"{Color.BLUE}[→] Đang tải ID {current_chapter_id}..."
                f"{Color.RESET}",
                end=" ",
                flush=True
            )

            # --- Tải HTML qua browser ---
            html = get_html(driver, url, is_first_request=is_first)

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

            # --- Parse HTML ---
            result = parse_chapter(html)

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
        base_url, story_id, start_chapter_id, num_chapters, output_dir = (
            get_user_input()
        )

        confirm = input(
            f"{Color.YELLOW}[?] Bắt đầu tải {num_chapters} chương? (Y/n): "
            f"{Color.RESET}"
        ).strip().lower()

        if confirm in ("n", "no"):
            print(f"{Color.DIM}[i] Đã hủy.{Color.RESET}")
            return

        download_chapters(
            base_url, story_id, start_chapter_id, num_chapters, output_dir
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
