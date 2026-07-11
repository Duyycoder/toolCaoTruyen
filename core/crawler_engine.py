import os
import sys
import time
import random
import re
import json
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
    safe_chapter_name = sanitize_filename(chapter_name)

    # Tên file = Chương + số chương (đệm 0 để tránh lỗi sắp xếp) + tên chương
    filename = f"Chương {chapter_index:04d} - {safe_chapter_name}.md"

    # Trực tiếp đặt file vào output_dir (chính là thư mục raw), không tạo thư mục con mang tên truyện
    os.makedirs(output_dir, exist_ok=True)

    # Format Markdown: chỉ chứa nội dung, không chứa tiêu đề chương (tránh lặp/thừa)
    md_content = f"{content}\n"

    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    return filepath


def find_last_chapter_index(output_dir: str) -> int:
    """Tìm số thứ tự chương lớn nhất trong các file .md đã lưu (kể cả bản dịch [VI])
    để tiếp tục đánh số khi không có file trạng thái hợp lệ.
    """
    max_index = 0
    try:
        for f in os.listdir(output_dir):
            if not f.endswith(".md"):
                continue
            match = re.match(r"Chương\s+(\d+)\s+-", f)
            if match:
                max_index = max(max_index, int(match.group(1)))
    except OSError:
        pass
    return max_index


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
    elif event == "continue":
        print(f"{Color.CYAN}[→] {event_data.get('message', '')}{Color.RESET}")
    elif event == "warn":
        print(f"{Color.YELLOW}{event_data.get('message', '')}{Color.RESET}")
    elif event == "error":
        print(f"{Color.RED}{event_data.get('message', '')}{Color.RESET}")
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
            full_path = os.path.abspath(output_dir)
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


def extract_chapter_id_from_url(url: str, fallback_id: Any) -> Any:
    """Trích xuất ID chương hoặc phần định danh chương từ URL phục vụ cho callback hiển thị.
    KHÔNG được dùng trong bất kỳ điều kiện if/while nào quyết định luồng chạy.
    """
    try:
        # Thử với 69shuba
        match = re.search(r"/txt/\d+/(\d+)", url)
        if match:
            return int(match.group(1))
        
        # Thử với metruyenchuvn: ví dụ: /nguoi-tren-van-nguoi/chuong-1-AoCo2t_YhnIh
        match2 = re.search(r"/(chuong-\d+-[A-Za-z0-9_]+|chuong-\d+)", url)
        if match2:
            return match2.group(1)
            
        # Thử tìm phần cuối cùng của URL
        parts = url.rstrip("/").split("/")
        if parts:
            return parts[-1]
    except Exception:
        pass
    return fallback_id


def download_chapters(
    base_url: str,
    story_id: int,
    start_chapter_id: Any,
    num_chapters: int,
    output_dir: str,
    parser: BaseSourceParser,
    progress_callback: Optional[Callable[[dict], None]] = None,
    is_stopped: Optional[Callable[[], bool]] = None,
    continue_download: bool = False
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

    # Khởi tạo URL chương đầu tiên từ ID người dùng nhập hoặc dùng trực tiếp nếu start_chapter_id là URL
    if isinstance(start_chapter_id, str) and (start_chapter_id.startswith("http://") or start_chapter_id.startswith("https://")):
        current_url: str = start_chapter_id
    elif isinstance(story_id, str) and (story_id.startswith("http://") or story_id.startswith("https://")):
        current_url: str = story_id
    else:
        current_url = parser.build_chapter_url(story_id, start_chapter_id)
    story_name = None
    successful_downloads: int = 0
    current_chapter_number: int = 0

    state_file = os.path.join(output_dir, ".crawler_state.json")
    # Kế hoạch tra mục lục (cần trình duyệt nên sẽ thực hiện sau khi khởi tạo Chrome)
    resume_plan: Optional[dict] = None
    if continue_download:
        state = None
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                state = None

        state_index = state.get("last_chapter_index", 0) if state else 0
        state_next_url = state.get("next_url") if state else None
        disk_index = find_last_chapter_index(output_dir)

        if state_next_url and state_index >= disk_index:
            # Link lưu sẵn còn mới -> dùng luôn, BỎ QUA điểm bắt đầu người dùng nhập
            current_url = state_next_url
            current_chapter_number = state_index
            progress_callback({
                "event": "continue",
                "message": f"Tiếp tục tải từ chương {current_chapter_number + 1} theo link đã lưu ({current_url})."
            })
        elif disk_index > 0:
            # Không có link lưu sẵn, hoặc link lưu sẵn CŨ hơn số chương đã có trên đĩa
            # (ví dụ do một lần tải lại từ đầu đã ghi đè trạng thái).
            # -> Tra mục lục truyện để tìm link chương disk_index + 1.
            resume_plan = {
                "target_index": disk_index,
                "fallback_url": state_next_url,
                "fallback_index": state_index
            }
        else:
            # Thư mục trống và không có trạng thái: không có gì để tiếp tục
            if state and state.get("reached_end"):
                progress_callback({
                    "event": "warn",
                    "message": "[!] Lần tải trước đã đến chương mới nhất của truyện."
                })
            else:
                progress_callback({
                    "event": "warn",
                    "message": "[!] Đã bật 'Tải tiếp' nhưng chưa có chương nào trên đĩa và không có trạng thái lưu sẵn. Sẽ tải từ điểm bắt đầu."
                })
            
    visited_urls = set()
    consecutive_failures = 0
    total_attempted = 0
    
    # --- Khởi tạo Chrome ---
    driver = create_browser()

    progress_callback({"event": "start", "message": "Bắt đầu tải truyện..."})

    abort = False
    try:
        # --- Tra mục lục để xác định link chương tiếp theo (nếu cần) ---
        if resume_plan is not None:
            target_index = resume_plan["target_index"]
            resolved = False
            progress_callback({
                "event": "continue",
                "message": f"Đang tra mục lục truyện để tìm link chương {target_index + 1}..."
            })
            try:
                book_url = parser.get_book_url(story_id, resume_plan.get("fallback_url"))
                if book_url:
                    catalog = parser.get_catalog(driver, book_url)
                    target = next((c for c in catalog if c.index == target_index + 1), None)
                    if target:
                        current_url = target.chapter_url
                        current_chapter_number = target_index
                        resolved = True
                        progress_callback({
                            "event": "continue",
                            "message": f"Tiếp tục tải từ chương {target_index + 1}: {target.title} ({current_url})"
                        })
                    elif catalog:
                        # Mục lục hợp lệ nhưng không có chương kế tiếp -> đã đến chương mới nhất
                        reached_end = True
                        abort = True
                        progress_callback({
                            "event": "warn",
                            "message": f"[!] Mục lục hiện có {len(catalog)} chương, chưa có chương {target_index + 1}. Truyện chưa ra chương mới."
                        })
            except NotImplementedError:
                pass
            except Exception as ex:
                progress_callback({
                    "event": "warn",
                    "message": f"[!] Lỗi khi tra mục lục truyện: {ex}"
                })

            if not resolved and not abort:
                if resume_plan.get("fallback_url"):
                    current_url = resume_plan["fallback_url"]
                    current_chapter_number = resume_plan.get("fallback_index", 0)
                    progress_callback({
                        "event": "warn",
                        "message": f"[!] Không tra được mục lục; dùng link đã lưu (từ chương {current_chapter_number + 1}). Một số chương có thể bị tải lại nhưng sẽ không bị dịch lại."
                    })
                elif str(start_chapter_id).strip().lower() not in ("", "auto"):
                    current_chapter_number = target_index
                    progress_callback({
                        "event": "continue",
                        "message": f"Không tra được mục lục; dùng điểm bắt đầu đã nhập ({start_chapter_id}) và tiếp tục đánh số từ chương {target_index + 1}."
                    })
                else:
                    # Không còn cách nào xác định đúng chương kế tiếp:
                    # DỪNG thay vì âm thầm tải lại từ chương 1
                    abort = True
                    progress_callback({
                        "event": "error",
                        "message": (
                            f"[✗] Không thể xác định link chương {target_index + 1} để tải tiếp "
                            f"(không có link lưu sẵn và không tra được mục lục). "
                            f"Hãy nhập URL chương {target_index + 1} vào ô 'Chương bắt đầu' rồi chạy lại."
                        )
                    })

        while not abort and successful_downloads < num_chapters:
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

            # --- Vòng lặp thử lại cùng một URL (tối đa 10 lần) ---
            MAX_PAGE_RETRIES = 10
            page_load_retry_count = 0
            load_success = False
            html = None
            result = None

            while page_load_retry_count < MAX_PAGE_RETRIES:
                total_attempted += 1
                is_first = (total_attempted == 1)

                retry_suffix = f" (thử lại {page_load_retry_count}/{MAX_PAGE_RETRIES - 1})" if page_load_retry_count > 0 else ""
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
                        "max_failures": MAX_PAGE_RETRIES,
                        "message": f"Chương không tồn tại hoặc lỗi mạng (thử lại {page_load_retry_count}/{MAX_PAGE_RETRIES})."
                    })
                else:
                    progress_callback({
                        "event": "chapter_empty",
                        "chapter_id": current_chapter_id,
                        "consecutive_failures": page_load_retry_count,
                        "max_failures": MAX_PAGE_RETRIES,
                        "message": f"Nội dung chương rỗng (thử lại {page_load_retry_count}/{MAX_PAGE_RETRIES})."
                    })

                time.sleep(random.uniform(0.5, 1.5))

            # --- Xử lý khi thất bại hoàn toàn 10 lần trên cùng 1 URL ---
            if not load_success:
                consecutive_failures += 1
                progress_callback({
                    "event": "error",
                    "message": f"[✗] Không thể tải chương ID {current_chapter_id} sau {MAX_PAGE_RETRIES} lần thử."
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
            current_chapter_number += 1
            filepath = save_to_markdown(
                output_dir, story_name, chapter_name,
                content, current_chapter_number
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

            # --- Lưu trạng thái (serialize trước khi mở file để không để lại file rỗng khi lỗi) ---
            try:
                state_payload = json.dumps({
                    "last_chapter_index": current_chapter_number,
                    "next_url": next_url,
                    "reached_end": next_url is None
                }, ensure_ascii=False)
                with open(state_file, "w", encoding="utf-8") as f:
                    f.write(state_payload)
            except Exception:
                pass

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

