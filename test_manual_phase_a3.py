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
        return "chuan_html"

    def parse_chapter(self, html: str) -> Optional[Tuple[str, str, str]]:
        return "Truyện Mock", "Chương Mock", "Nội dung chương mock dài hơn 50 ký tự để vượt qua bộ lọc của crawler."

    def is_valid_response(self, html: str) -> bool:
        return True

    def get_next_chapter_url(self, driver: Any) -> Optional[str]:
        import re
        match = re.search(r"/(\d+)$", self.current_url)
        if match:
            next_id = int(match.group(1)) + 1
            return f"https://mocksite.com/txt/123/{next_id}"
        return "https://mocksite.com/txt/123/40755199"


def run_tests():
    print("==================================================")
    print("   CHẠY KIỂM THỬ THỦ CÔNG: PHASE A3 STOP FLAG")
    print("==================================================")

    parser = MockParser(base_url="https://mocksite.com/txt")
    events = []
    stopped = False

    def test_callback(event_data: dict) -> None:
        events.append(event_data)
        print(f"      [Callback]: {event_data.get('event')} -> {event_data.get('message')}")
        
        # Khi tải thành công chương 1, lập tức kích hoạt cờ dừng
        if event_data.get("event") == "chapter_success":
            nonlocal stopped
            stopped = True
            print("      [Test Control]: Đã kích hoạt cờ dừng (stopped = True)")

    def is_stopped_check() -> bool:
        return stopped

    # Yêu cầu tải 5 chương, nhưng cờ dừng sẽ ngắt quá trình tải sau 1 chương thành công
    print("[+] Khởi chạy download_chapters và giả lập dừng sau 1 chương...")
    download_chapters(
        base_url="https://mocksite.com/txt",
        story_id=123,
        start_chapter_id=40755198,
        num_chapters=5,
        output_dir="./mock_downloads_a3",
        parser=parser,
        progress_callback=test_callback,
        is_stopped=is_stopped_check
    )

    print("\n[+] Đang xác thực trình tự sự kiện khi có tín hiệu dừng...")
    event_names = [e["event"] for e in events]
    print(f"    Trình tự sự kiện nhận được: {event_names}")

    # Xác thực:
    # 1. Sự kiện start
    assert event_names[0] == "start"
    
    # 2. Sự kiện tải chương 1 thành công
    assert "chapter_success" in event_names
    
    # 3. Phải nhận được sự kiện 'stopped'
    assert "stopped" in event_names, "Lỗi: Không nhận được sự kiện dừng 'stopped'"
    
    # 4. Phải nhận được sự kiện 'complete' ở cuối
    assert event_names[-1] == "complete", "Lỗi: Sự kiện cuối cùng phải là 'complete'"

    # 5. Số chương tải thành công chỉ được là 1 (dù yêu cầu 5)
    complete_event = events[-1]
    assert complete_event["successful_downloads"] == 1, f"Lỗi: Số chương tải được là {complete_event['successful_downloads']} thay vì 1"
    
    print("    [✓] Kiểm thử cờ dừng đạt chuẩn (PASSED)")

    # Dọn dẹp
    import os
    import shutil
    if os.path.exists("./mock_downloads_a3"):
        shutil.rmtree("./mock_downloads_a3")

    print("\n==================================================")
    print("   TẤT CẢ CÁC BÀI KIỂM THỬ THÀNH CÔNG (SUCCESS)")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
