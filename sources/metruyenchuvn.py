import time
import random
import re
from typing import Optional, Tuple, Any
from bs4 import BeautifulSoup
from sources.base import BaseSourceParser, Color, BookSearchResult, ChapterInfo

class MetruyenchuvnParser(BaseSourceParser):
    def __init__(self, base_url: str):
        """Khởi tạo parser với Base URL của truyện."""
        self.base_url = base_url.rstrip("/")

    def build_chapter_url(self, story_id: int, chapter_id: int) -> str:
        """Với metruyenchuvn, ta chủ yếu dùng URL cào trực tiếp dán vào,
        nhưng phương thức này vẫn cần thiết để tương thích interface cũ.
        """
        # Hỗ trợ fallback nếu truyền dạng số
        return f"{self.base_url}/chuong-{chapter_id}"

    def get_html(
        self,
        driver: Any,
        url: str,
        is_first_request: bool = False
    ) -> Optional[str]:
        """Tải mã nguồn HTML từ URL sử dụng Selenium Driver, tự động bypass Cloudflare."""
        try:
            driver.get(url)

            # Chờ Cloudflare challenge tự giải quyết
            max_wait = 30 if is_first_request else 10
            for i in range(max_wait):
                title = driver.title or ""
                if "Just a moment" in title:
                    if i == 0 and is_first_request:
                        print(
                            f"{Color.YELLOW}[⏳] Đang vượt Cloudflare metruyenchuvn..."
                            f"{Color.RESET}",
                            end=" ",
                            flush=True
                        )
                    time.sleep(1)
                    continue

                if title and "Just a moment" not in title:
                    if is_first_request and i > 0:
                        print(f"{Color.GREEN}OK!{Color.RESET}")
                    break

                time.sleep(0.5)

            final_title = driver.title or ""
            if "Just a moment" in final_title:
                if is_first_request:
                    print(f"{Color.RED}Thất bại vượt Cloudflare!{Color.RESET}")
                return None

            html = driver.page_source
            if not self.is_valid_response(html):
                return None

            return html

        except Exception as e:
            print(f"{Color.RED}[✗] Lỗi trình duyệt khi tải trang: {e}{Color.RESET}")
            return None

    def is_valid_response(self, html: str) -> bool:
        """Kiểm tra phản hồi có hợp lệ hay không. Phải chứa div.truyen"""
        if not html or len(html) < 500:
            return False
        if "div" not in html or ("class=\"truyen\"" not in html and "class='truyen'" not in html):
            # Một số trang có cấu trúc khác, kiểm tra class truyen
            soup = BeautifulSoup(html, "html.parser")
            if not soup.select_one("div.truyen"):
                return False
        return True

    def parse_chapter(self, html: str) -> Optional[Tuple[str, str, str]]:
        """Phân tích cú pháp HTML và trả về (tên_truyện, tên_chương, nội_dung_làm_sạch)."""
        soup = BeautifulSoup(html, "html.parser")

        # 1. Tên truyện
        story_name = "Unknown"
        # Thử tìm trong h1.current-book
        story_h1 = soup.select_one("h1.current-book a, h1.current-book, h1")
        if story_h1:
            story_name = story_h1.get_text(strip=True)
        
        # Fallback từ breadcrumb: thường phần tử thứ 2 là tên truyện
        breadcrumbs = soup.select(".breadcrumb a, .bread a")
        if (story_name == "Unknown" or not story_name) and len(breadcrumbs) >= 2:
            story_name = breadcrumbs[1].get_text(strip=True)
            
        story_name = story_name.strip()

        # 2. Tên chương
        chapter_name = ""
        chapter_h2 = soup.select_one("h2.current-chapter a, h2.current-chapter, h2")
        if chapter_h2:
            chapter_name = chapter_h2.get_text(strip=True)

        if not chapter_name and len(breadcrumbs) >= 3:
            chapter_name = breadcrumbs[2].get_text(strip=True)

        if not chapter_name:
            if soup.title:
                title_parts = soup.title.get_text(strip=True).split("-")
                if len(title_parts) >= 2:
                    chapter_name = title_parts[1].strip()

        if not chapter_name:
            return None  # Không có tên chương hợp lệ

        chapter_name = chapter_name.strip()

        # 3. Nội dung chương
        content_div = soup.select_one("div.truyen")
        if not content_div:
            return None

        # Làm sạch nội dung
        # Loại bỏ các thẻ không cần thiết
        for tag in content_div.find_all(["script", "style", "iframe", "ins", "noscript"]):
            tag.decompose()

        # Thay thế <br> thành newline
        for br in content_div.find_all("br"):
            br.replace_with("\n")

        # Thay thế <p> thành newline kép
        for p in content_div.find_all("p"):
            p.insert_before("\n\n")
            p.insert_after("\n\n")

        raw_text = content_div.get_text()
        
        # Tách dòng và làm sạch khoảng trắng
        lines = raw_text.split("\n")
        cleaned_lines = []
        for line in lines:
            line_stripped = line.strip()
            # Bỏ các quảng cáo/text rác nếu cần
            if not line_stripped:
                cleaned_lines.append("")
                continue
            cleaned_lines.append(line_stripped)

        content_text = "\n".join(cleaned_lines)
        content_text = re.sub(r"\n{3,}", "\n\n", content_text)
        content_text = content_text.strip()

        if len(content_text) < 50:
            return None

        return story_name, chapter_name, content_text

    def get_next_chapter_url(self, driver: Any) -> Optional[str]:
        """Lấy URL của chương tiếp theo từ driver."""
        try:
            # Thử tìm thẻ a có chữ "Chương tiếp" hoặc chứa "tiếp"
            from selenium.webdriver.common.by import By
            elements = driver.find_elements(By.XPATH, "//a[contains(text(), 'Chương tiếp') or contains(text(), 'Tiếp')]")
            for el in elements:
                href = el.get_attribute("href")
                if href and href.strip() and href.strip() != "#":
                    return href.strip()

            # Fallback dùng BeautifulSoup
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a"):
                text = a.get_text(strip=True)
                if "Chương tiếp" in text or "tiếp" in text.lower() or "tiếp 》" in text:
                    href = a.get("href", "").strip()
                    if href and href != "#":
                        from urllib.parse import urljoin
                        return urljoin(driver.current_url, href)
            return None
        except Exception as e:
            print(f"\n{Color.RED}[✗] Lỗi khi xác định chương kế tiếp: {e}{Color.RESET}")
            return None
