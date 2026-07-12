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
import re
import sys
from typing import Tuple

from sources.base import Color
from sources.registry import SOURCES, get_source
from core.config_manager import (
    load_config,
    save_config,
    DEFAULT_BASE_URL,
    DEFAULT_OUTPUT_DIR
)
from core.crawler_engine import download_chapters

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
    url_mode = False

    # --- Hỏi chế độ cào hoặc dùng cấu hình cũ ---
    if config:
        prev_base_url = config.get("base_url", DEFAULT_BASE_URL)
        prev_output_dir = config.get("output_dir", DEFAULT_OUTPUT_DIR)
        prev_source = config.get("source", "69shuba")

        print(f"{Color.BLUE}[i] Phát hiện cấu hình lần chạy trước:{Color.RESET}")
        print(f"    Nguồn     : {Color.CYAN}{prev_source}{Color.RESET}")
        print(f"    Base URL  : {Color.CYAN}{prev_base_url}{Color.RESET}")
        print(f"    Thư mục   : {Color.CYAN}{prev_output_dir}{Color.RESET}")

        reuse = input(
            f"\n{Color.YELLOW}[?] Dùng lại cấu hình trên? (Y/n) hoặc gõ 'url' để dán link chương trực tiếp: {Color.RESET}"
        ).strip().lower()
        if reuse in ("", "y", "yes"):
            base_url = prev_base_url
            output_dir = prev_output_dir
            source = prev_source
            print(f"{Color.GREEN}[✓] Đã tải lại cấu hình.{Color.RESET}\n")
        elif reuse == "url":
            print(f"{Color.DIM}[i] Chuyển sang chế độ dán URL trực tiếp.{Color.RESET}\n")
            config = None
            # Đánh dấu là chạy bằng dán URL
            url_mode = True
        else:
            print(f"{Color.DIM}[i] Bỏ qua cấu hình cũ. Nhập cấu hình mới:{Color.RESET}\n")
            config = None
            url_mode = False
    else:
        url_mode = False

    # Nếu người dùng muốn cào bằng cách dán URL trực tiếp
    if not config:
        if not url_mode:
            # Hỏi xem họ có muốn dán URL trực tiếp không
            url_choice = input(
                f"{Color.YELLOW}[?] Bạn có muốn dán trực tiếp URL chương truyện để cào luôn không? (y/N): {Color.RESET}"
            ).strip().lower()
            if url_choice in ("y", "yes"):
                url_mode = True

        if url_mode:
            while True:
                direct_url = input(
                    f"{Color.YELLOW}[?] Nhập URL chương truyện cần cào: {Color.RESET}"
                ).strip()
                if not direct_url.startswith("http"):
                    print(f"{Color.RED}[!] URL không hợp lệ. Phải bắt đầu bằng http:// hoặc https://{Color.RESET}")
                    continue
                break

            # Tự động nhận diện nguồn dựa vào URL
            if "metruyenchuvn.com" in direct_url:
                source = "metruyenchuvn"
                # Lấy base_url từ domain + tên truyện (ví dụ: https://metruyenchuvn.com/nguoi-tren-van-nguoi)
                # URL: https://metruyenchuvn.com/nguoi-tren-van-nguoi/chuong-1-AoCo2t_YhnIh
                # Cắt bớt phần chương ở cuối
                match = re.match(r"(https?://[^/]+/[^/]+)/chuong-", direct_url)
                if match:
                    base_url = match.group(1)
                else:
                    # Fallback
                    parts = direct_url.split("/")
                    base_url = "/".join(parts[:4])
            elif "69shuba" in direct_url or "69shu" in direct_url:
                source = "69shuba"
                # URL dạng: https://www.69shuba.com/txt/30756/30756382
                parts = direct_url.split("/")
                base_url = "/".join(parts[:5]) # https://www.69shuba.com/txt
            else:
                # Mặc định là metruyenchuvn nếu không rõ
                source = "metruyenchuvn"
                parts = direct_url.split("/")
                base_url = "/".join(parts[:4])

            story_id = direct_url  # Đưa URL này vào story_id để crawler_engine nhận diện làm điểm xuất phát
            start_chapter_id = direct_url
        else:
            # --- Nhập Nguồn truyện (nếu chưa dùng config cũ) ---
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

    # --- Chọn chế độ nhập truyện (nếu nguồn hỗ trợ tìm kiếm và không ở chế độ dán URL trực tiếp) ---
    if not config and not url_mode:
        supports_search = source in ("69shuba",)
        
        if supports_search:
            print(f"\n{Color.YELLOW}[?] Cách nhập thông tin truyện:{Color.RESET}")
            print(f"    {Color.CYAN}1{Color.RESET} — Nhập ID truyện và ID chương bắt đầu thủ công")
            print(f"    {Color.CYAN}2{Color.RESET} — Tìm kiếm truyện theo tên (khuyên dùng)")
            
            mode = input(f"{Color.YELLOW}[?] Chọn (1/2, mặc định: 2): {Color.RESET}").strip()
            if mode == "1":
                story_id, start_chapter_id = _input_ids_manual()
            else:
                story_id, start_chapter_id = _search_and_select(source, base_url)
        else:
            story_id, start_chapter_id = _input_ids_manual()

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

    # --- Lưu config cho lần chạy sau (chỉ lưu nếu không phải chế độ dán URL tạm thời, hoặc lưu base_url hợp lệ) ---
    if not isinstance(story_id, str) or not story_id.startswith("http"):
        save_config(base_url, output_dir, source)
    else:
        # Đối với chế độ dán URL trực tiếp, vẫn lưu source và output_dir
        save_config(base_url, output_dir, source)

    # --- Hiển thị tóm tắt ---
    print(f"\n{Color.CYAN}{'─' * 60}{Color.RESET}")
    print(f"{Color.BOLD}   📋  TÓM TẮT CẤU HÌNH:{Color.RESET}")
    print(f"   Nguồn truyện    : {Color.GREEN}{source}{Color.RESET}")
    print(f"   Base URL        : {Color.GREEN}{base_url}{Color.RESET}")
    if isinstance(story_id, str) and story_id.startswith("http"):
        print(f"   URL bắt đầu cào : {Color.GREEN}{story_id}{Color.RESET}")
    else:
        print(f"   ID Truyện       : {Color.GREEN}{story_id}{Color.RESET}")
        print(f"   Chương bắt đầu  : {Color.GREEN}{start_chapter_id}{Color.RESET}")
    print(f"   Số chương tải   : {Color.GREEN}{num_chapters}{Color.RESET}")
    print(f"   Thư mục lưu     : {Color.GREEN}{output_dir}{Color.RESET}")
    print(f"{Color.CYAN}{'─' * 60}{Color.RESET}\n")

    return base_url, story_id, start_chapter_id, num_chapters, output_dir, source


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

        # Chạy tải chương (dùng callback in console mặc định)
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


def _input_ids_manual() -> Tuple[int, int]:
    """Nhập ID truyện và ID chương bắt đầu thủ công."""
    while True:
        story_id_str = input(
            f"{Color.YELLOW}[?] ID Truyện "
            f"{Color.DIM}(ví dụ: 90438){Color.RESET}: "
        ).strip()
        if story_id_str.isdigit() and int(story_id_str) > 0:
            story_id = int(story_id_str)
            break
        print(f"{Color.RED}[!] ID Truyện phải là số nguyên dương.{Color.RESET}")

    while True:
        chapter_id_str = input(
            f"{Color.YELLOW}[?] ID Chương bắt đầu "
            f"{Color.DIM}(ví dụ: 40755198){Color.RESET}: "
        ).strip()
        if chapter_id_str.isdigit() and int(chapter_id_str) > 0:
            start_chapter_id = int(chapter_id_str)
            break
        print(f"{Color.RED}[!] ID Chương phải là số nguyên dương.{Color.RESET}")
        
    return story_id, start_chapter_id


def _search_and_select(source: str, base_url: str) -> Tuple[int, int]:
    """Tìm kiếm truyện theo tên → chọn truyện → tải mục lục → chọn chương."""
    from sources.book_search import BookSearcher
    from core.intelligent_search import translate_query_to_chinese, generate_alternative_chinese_names
    
    parser = get_source(source, base_url)
    
    with BookSearcher(parser) as searcher:
        while True:
            keyword = input(
                f"\n{Color.YELLOW}[?] Nhập tên truyện cần tìm "
                f"{Color.DIM}(Tiếng Việt hoặc Tiếng Trung){Color.RESET}: "
            ).strip()
            
            if not keyword:
                print(f"{Color.RED}[!] Tên truyện không được để trống.{Color.RESET}")
                continue
                
            # Dịch sang tiếng Trung nếu nhập tiếng Việt
            translated_keyword = translate_query_to_chinese(keyword)
            if translated_keyword != keyword:
                print(f"{Color.CYAN}[i] Đã chuyển ngữ truy vấn: '{keyword}' -> '{translated_keyword}'{Color.RESET}")
                
            print(f"\n{Color.BLUE}[⏳] Đang tìm kiếm '{translated_keyword}' trên {source}...{Color.RESET}")
            results = searcher.search(translated_keyword)
            
            # Thử lại tối đa 10 lần bằng LLM nếu không có kết quả
            failed_attempts = [keyword]
            if translated_keyword != keyword:
                failed_attempts.append(translated_keyword)
                
            retry_count = 0
            max_retries = 10
            
            while not results and retry_count < max_retries:
                retry_count += 1
                print(f"{Color.YELLOW}[!] Không tìm thấy kết quả cho '{translated_keyword}'.{Color.RESET}")
                print(f"{Color.BLUE}[⏳] Lần thử {retry_count}/{max_retries}: LLM đang tìm tên thay thế...{Color.RESET}")
                
                alternatives = generate_alternative_chinese_names(keyword, failed_attempts)
                if not alternatives:
                    print(f"{Color.RED}[!] LLM không thể tìm thêm tên thay thế nào.{Color.RESET}")
                    break
                    
                print(f"{Color.CYAN}[i] Các từ khóa gợi ý: {', '.join(alternatives)}{Color.RESET}")
                
                found_any = False
                for alt in alternatives:
                    if alt in failed_attempts:
                        continue
                    failed_attempts.append(alt)
                    print(f"    - Đang thử từ khóa: '{alt}'...")
                    results = searcher.search(alt)
                    if results:
                        print(f"{Color.GREEN}[✓] Tìm thấy truyện với tên gợi ý: '{alt}'!{Color.RESET}")
                        found_any = True
                        break
                if found_any:
                    break
                    
            if not results:
                print(f"\n{Color.RED}[✗] Đã thử {max_retries} lần tìm kiếm bằng tên truyện vẫn không tìm thấy kết quả.{Color.RESET}")
                retry_choice = input(
                    f"{Color.YELLOW}[?] Bạn muốn làm gì? (1: Tìm từ khóa khác, 2: Nhập ID thủ công, mặc định: 2): {Color.RESET}"
                ).strip()
                if retry_choice == "1":
                    continue
                else:
                    return _input_ids_manual()
                    
            selected = _display_search_results(results)
            if selected is None:
                continue
                
            print(f"\n{Color.BLUE}[⏳] Đang tải mục lục chương...{Color.RESET}")
            catalog = searcher.get_catalog(selected.book_url)
            
            if not catalog:
                print(f"{Color.YELLOW}[!] Không lấy được mục lục. Hãy nhập ID chương thủ công.{Color.RESET}")
                story_id = int(selected.book_id)
                _, start_chapter_id = _input_ids_manual()
                return story_id, start_chapter_id
                
            return _display_catalog_and_choose(selected, catalog)


def _display_search_results(results: list) -> Optional[Any]:
    """Hiển thị danh sách kết quả tìm kiếm và trả về truyện được chọn."""
    from typing import Any
    print(f"\n{Color.CYAN}{'═' * 60}{Color.RESET}")
    print(f"{Color.BOLD}   📚  KẾT QUẢ TÌM KIẾM ({len(results)} truyện){Color.RESET}")
    print(f"{Color.CYAN}{'═' * 60}{Color.RESET}\n")
    
    for i, r in enumerate(results, 1):
        print(f"  {Color.CYAN}[{i}]{Color.RESET} {Color.BOLD}{r.title}{Color.RESET}")
        info_parts = [f"Tác giả: {r.author}"]
        info_parts.append(f"ID: {r.book_id}")
        if r.status:
            info_parts.append(r.status)
        print(f"      {Color.DIM}{' | '.join(info_parts)}{Color.RESET}\n")
        
    print(f"{Color.CYAN}{'─' * 60}{Color.RESET}")
    
    while True:
        choice = input(
            f"{Color.YELLOW}[?] Chọn truyện (1-{len(results)}), "
            f"hoặc 's' để tìm từ khóa khác: {Color.RESET}"
        ).strip().lower()
        
        if choice == 's':
            return None
            
        if choice.isdigit() and 1 <= int(choice) <= len(results):
            return results[int(choice) - 1]
            
        print(f"{Color.RED}[!] Lựa chọn không hợp lệ.{Color.RESET}")


def _display_catalog_and_choose(selected: Any, catalog: list) -> Tuple[int, int]:
    """Hiển thị mục lục và cho người dùng chọn chương bắt đầu."""
    total = len(catalog)
    
    print(f"\n{Color.CYAN}{'═' * 60}{Color.RESET}")
    print(f"{Color.BOLD}   📋  MỤC LỤC — {selected.title} ({total} chương){Color.RESET}")
    print(f"{Color.CYAN}{'═' * 60}{Color.RESET}\n")
    
    def _print_chapter(ch):
        print(f"  {Color.DIM}{ch.index:>4}{Color.RESET} | "
              f"ID: {Color.CYAN}{ch.chapter_id}{Color.RESET} | "
              f"{ch.title}")
              
    if total <= 30:
        for ch in catalog:
            _print_chapter(ch)
    else:
        for ch in catalog[:15]:
            _print_chapter(ch)
        print(f"\n  {Color.DIM}... (ẩn {total - 25} chương) ...{Color.RESET}\n")
        for ch in catalog[-10:]:
            _print_chapter(ch)
            
    print(f"\n{Color.CYAN}{'─' * 60}{Color.RESET}")
    
    if total > 30:
        show_all = input(
            f"{Color.DIM}[?] Nhập 'all' để xem toàn bộ mục lục, "
            f"Enter để tiếp tục: {Color.RESET}"
        ).strip().lower()
        if show_all == 'all':
            for ch in catalog:
                _print_chapter(ch)
            print(f"\n{Color.CYAN}{'─' * 60}{Color.RESET}")
            
    id_to_chapter = {ch.chapter_id: ch for ch in catalog}
    index_to_chapter = {ch.index: ch for ch in catalog}
    
    while True:
        user_input = input(
            f"\n{Color.YELLOW}[?] Chương bắt đầu cào "
            f"{Color.DIM}(nhập số thứ tự STT 1-{total} hoặc paste Chapter ID){Color.RESET}: "
        ).strip()
        
        if not user_input.isdigit():
            print(f"{Color.RED}[!] Vui lòng nhập số.{Color.RESET}")
            continue
            
        num = int(user_input)
        
        if num <= total and num in index_to_chapter:
            chosen = index_to_chapter[num]
            start_chapter_id = int(chosen.chapter_id)
            print(f"  {Color.GREEN}→ Đã chọn STT {num}: "
                  f"{chosen.title} (ID: {chosen.chapter_id}){Color.RESET}")
        elif str(num) in id_to_chapter:
            chosen = id_to_chapter[str(num)]
            start_chapter_id = num
            print(f"  {Color.GREEN}→ Đã chọn Chapter ID {num}: "
                  f"{chosen.title} (STT: {chosen.index}){Color.RESET}")
        else:
            print(f"{Color.YELLOW}[!] Không tìm thấy trong mục lục.{Color.RESET}")
            confirm = input(
                f"{Color.YELLOW}    Bạn có chắc muốn dùng Chapter ID {num}? (y/n): {Color.RESET}"
            ).strip().lower()
            if confirm in ('y', 'yes', ''):
                start_chapter_id = num
            else:
                continue
        break
        
    story_id = int(selected.book_id)
    return story_id, start_chapter_id


if __name__ == "__main__":
    main()
