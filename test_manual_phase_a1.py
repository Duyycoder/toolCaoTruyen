import sys
from typing import Optional, Tuple, Any

# Mock webdriver creation before importing core.crawler_engine
import core.crawler_engine

class MockDriver:
    def quit(self):
        pass

# Monkey-patch create_browser để tránh khởi chạy Chrome thật
core.crawler_engine.create_browser = lambda: MockDriver()

from sources.base import BaseSourceParser
from core.crawler_engine import download_chapters

class MockParser(BaseSourceParser):
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.current_url = ""

    def build_chapter_url(self, story_id: int, chapter_id: int) -> str:
        return f"{self.base_url}/{story_id}/{chapter_id}"

    def get_html(self, driver: Any, url: str, is_first_request: bool = False) -> Optional[str]:
        self.current_url = url
        # Mock HTML cho chương 1 và chương 2
        if "40755198" in url:
            return "chuan_1"
        elif "40755199" in url:
            return "chuan_2"
        # Trả về None để mô phỏng lỗi 404 cho các chương tiếp theo
        return None

    def parse_chapter(self, html: str) -> Optional[Tuple[str, str, str]]:
        if html == "chuan_1":
            return "Truyện Mock", "Chương 1", "Nội dung chương 1 dài hơn 50 ký tự để vượt qua bộ lọc của crawler."
        elif html == "chuan_2":
            return "Truyện Mock", "Chương 2", "Nội dung chương 2 dài hơn 50 ký tự để vượt qua bộ lọc của crawler."
        return None

    def is_valid_response(self, html: str) -> bool:
        return True

    def get_next_chapter_url(self, driver: Any) -> Optional[str]:
        if "40755198" in self.current_url:
            return "https://mocksite.com/txt/123/40755199"
        elif "40755199" in self.current_url:
            return "https://mocksite.com/txt/123/40755200"
        return None


def run_tests():
    print("==================================================")
    print("   CHẠY KIỂM THỬ THỦ CÔNG: PHASE A1 REFACTOR")
    print("==================================================")

    parser = MockParser(base_url="https://mocksite.com/txt")
    events = []

    def test_callback(event_data: dict) -> None:
        events.append(event_data)
        # Đồng thời in ra màn hình để quan sát trực quan
        print(f"      [Event Callback]: {event_data.get('event')} -> {event_data.get('message')}")

    # Tải 3 chương, bắt đầu từ ID 40755198
    # Chương 1 & 2 sẽ thành công. Chương 3 sẽ lỗi liên tiếp và dừng tiến trình
    print("[+] Khởi chạy download_chapters với MockParser và Callback giả lập...")
    download_chapters(
        base_url="https://mocksite.com/txt",
        story_id=123,
        start_chapter_id=40755198,
        num_chapters=3,
        output_dir="./mock_downloads",
        parser=parser,
        progress_callback=test_callback
    )

    print("\n[+] Đang xác thực trình tự sự kiện (events order)...")

    # Xác thực chuỗi sự kiện nhận được
    event_names = [e["event"] for e in events]
    print(f"    Trình tự sự kiện nhận được: {event_names}")

    # 1. Sự kiện bắt đầu
    assert event_names[0] == "start", "Lỗi: Sự kiện đầu tiên phải là 'start'"

    # 2. Trước tải chương 1
    assert events[1]["event"] == "before_download"
    assert events[1]["chapter_id"] == 40755198

    # 3. Sự kiện nhận được tên truyện
    assert events[2]["event"] == "story_name"
    assert events[2]["story_name"] == "Truyện Mock"

    # 4. Tải thành công chương 1
    assert events[3]["event"] == "chapter_success"
    assert events[3]["chapter_name"] == "Chương 1"

    # 5. Sự kiện delay trước chương tiếp theo
    assert events[4]["event"] == "delay"

    # 6. Trước tải chương 2
    assert events[5]["event"] == "before_download"
    assert events[5]["chapter_id"] == 40755199

    # 7. Tải thành công chương 2
    assert events[6]["event"] == "chapter_success"
    assert events[6]["chapter_name"] == "Chương 2"

    # 8. Sự kiện delay
    assert events[7]["event"] == "delay"

    # 9. Tải chương 3 (ID 40755200) -> thất bại (không tồn tại) 10 lần
    idx = 8
    for i in range(10):
        assert events[idx]["event"] == "before_download"
        assert events[idx]["chapter_id"] == 40755200
        idx += 1
        
        assert events[idx]["event"] == "chapter_not_exist"
        assert events[idx]["chapter_id"] == 40755200
        assert events[idx]["consecutive_failures"] == i + 1
        idx += 1

    # 10. Lỗi hoàn toàn
    assert events[idx]["event"] == "error"
    idx += 1

    # 11. Sự kiện hoàn tất
    assert events[idx]["event"] == "complete"
    assert events[idx]["successful_downloads"] == 2
    assert events[idx]["total_attempted"] == 12  # 2 thành công + 10 lỗi thử lại

    print("    [✓] Trình tự sự kiện đạt chuẩn (PASSED)")

    # Dọn dẹp thư mục mock_downloads tạo ra khi test
    import shutil
    if os.path.exists("./mock_downloads"):
        shutil.rmtree("./mock_downloads")

    print("\n==================================================")
    print("   TẤT CẢ CÁC BÀI KIỂM THỬ THÀNH CÔNG (SUCCESS)")
    print("==================================================")

if __name__ == "__main__":
    import os
    run_tests()
