import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from sources.metruyenchuvn import MetruyenchuvnParser
from core.crawler_engine import create_browser

def test_parser():
    print("[INFO] Bắt đầu test parser metruyenchuvn...")
    
    url = "https://metruyenchuvn.com/nguoi-tren-van-nguoi/chuong-1-AoCo2t_YhnIh"
    
    parser = MetruyenchuvnParser("https://metruyenchuvn.com/nguoi-tren-van-nguoi")
    
    driver = create_browser()
    
    try:
        print(f"[INFO] Tải URL: {url}")
        html = parser.get_html(driver, url, is_first_request=True)
        
        if not html:
            print("[ERROR] Không tải được HTML hoặc Cloudflare challenge block!")
            return
            
        print("[SUCCESS] Đã tải được HTML. Bắt đầu parse...")
        result = parser.parse_chapter(html)
        
        if not result:
            print("[ERROR] Parse thất bại! Trả về None.")
            return
            
        story_name, chapter_name, content = result
        print("\n=== KẾT QUẢ PARSE ===")
        print(f"Tên truyện: {story_name}")
        print(f"Tên chương: {chapter_name}")
        print(f"Độ dài nội dung: {len(content)} ký tự")
        print("\nXem trước nội dung:")
        print(content[:500])
        print("======================\n")
        
        print("[INFO] Đang tìm URL chương kế tiếp...")
        next_url = parser.get_next_chapter_url(driver)
        print(f"URL chương tiếp theo: {next_url}")
        
        if next_url == "https://metruyenchuvn.com/nguoi-tren-van-nguoi/chuong-2-OJOSrV8bDcK4":
            print("[SUCCESS] Nhận diện chương tiếp theo chính xác!")
        else:
            print(f"[WARN] Chương tiếp theo không khớp mong đợi. Kết quả nhận được: {next_url}")
            
    finally:
        driver.quit()
        print("[INFO] Đã đóng trình duyệt.")

if __name__ == "__main__":
    test_parser()
