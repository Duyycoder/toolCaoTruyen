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


if __name__ == "__main__":
    main()
