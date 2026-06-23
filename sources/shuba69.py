import time
import random
import re
from typing import Optional, Tuple, Any
from bs4 import BeautifulSoup
from sources.base import BaseSourceParser, Color

class Shuba69Parser(BaseSourceParser):
    # Các chuỗi rác/quảng cáo thường xuất hiện trên 69shuba, cần loại bỏ
    AD_PATTERNS = [
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

    def __init__(self, base_url: str):
        """Khởi tạo parser với Base URL của truyện."""
        self.base_url = base_url.rstrip("/")

    def build_chapter_url(self, story_id: int, chapter_id: int) -> str:
        """Tạo URL đầy đủ của chương truyện từ ID truyện và ID chương."""
        return f"{self.base_url}/{story_id}/{chapter_id}"

    def get_html(
        self,
        driver: Any,
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
            if not self.is_valid_response(html):
                return None

            # Kiểm tra trang 404 (chương bị xóa / không tồn tại)
            # So khớp chính xác "69书吧_404" hoặc "404" để tránh nhận nhầm chương 404 (ví dụ: 第404章)
            final_title_strip = final_title.strip()
            if final_title_strip == "69书吧_404" or final_title_strip == "404" or "找不到" in final_title or "不存在" in final_title:
                return None

            return html

        except Exception as e:
            print(f"{Color.RED}[✗] Lỗi trình duyệt: {e}{Color.RESET}")
            return None

    def is_valid_response(self, html: str) -> bool:
        """Kiểm tra xem HTML phản hồi có hợp lệ hay không.
        Với 69shuba, HTML phải có độ dài tối thiểu và chứa thẻ txtnav hoặc txtright.
        """
        if not html or len(html) < 500:
            return False
        # Kiểm tra có nội dung truyện hay không
        # (div.txtnav hoặc div#txtright là selector chính của 69shuba)
        if "txtnav" not in html and "txtright" not in html:
            return False
        return True

    def parse_chapter(self, html: str) -> Optional[Tuple[str, str, str]]:
        """Phân tích HTML để trích xuất tên truyện, tên chương và nội dung.
        Sử dụng BeautifulSoup4 với các CSS Selector phù hợp cho 69shuba.com.

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
        # Đây là nguồn ĐÁNG TIN CẬY NHẤT cho tên truyện/chương
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
        if story_name == "Unknown":
            breadcrumb = soup.select_one("div.bread")
            if breadcrumb:
                links = breadcrumb.find_all("a")
                if len(links) >= 2:
                    story_name = links[-1].get_text(strip=True)
                elif len(links) == 1:
                    story_name = links[0].get_text(strip=True)

        # --- Tên truyện fallback: <title> ---
        if story_name == "Unknown" and soup.title:
            title_text = soup.title.get_text(strip=True)
            parts = title_text.split("-")
            if len(parts) >= 2:
                story_name = parts[0].strip()

        # --- Tên chương fallback: <h1 class="hide720"> ---
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
        content_text = self._clean_content(content_div)

        if not content_text or len(content_text.strip()) < 50:
            return None

        return story_name, chapter_name, content_text

    def _clean_content(self, content_div: BeautifulSoup) -> str:
        """Làm sạch nội dung HTML: loại bỏ quảng cáo, chuyển đổi thẻ HTML
        thành format Markdown phù hợp.
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
            for pattern in self.AD_PATTERNS:
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

    def get_next_chapter_url(self, driver: Any) -> Optional[str]:
        """Lấy URL của chương tiếp theo bằng cách tìm phần tử nút 'chương sau'
        qua Selenium, đọc thuộc tính href.
        """
        try:
            from selenium.webdriver.common.by import By
            # Thử tìm phần tử a chứa chữ "下一章" qua Selenium
            element = None
            try:
                # Ưu tiên tìm trong div.page1 chứa class trang điều hướng
                element = driver.find_element(By.XPATH, "//div[contains(@class, 'page1')]/a[contains(text(), '下一章')]")
            except Exception:
                pass

            if not element:
                try:
                    # Fallback tìm bất kỳ thẻ a nào chứa "下一章"
                    element = driver.find_element(By.XPATH, "//a[contains(text(), '下一章')]")
                except Exception:
                    pass

            if element:
                href = element.get_attribute("href")
                if href:
                    href = href.strip()
                    # Loại bỏ URL không chứa '/txt/' (ví dụ trỏ sang trang detail /book/ hoặc list)
                    if "/txt/" not in href:
                        return None
                    return href

            # Fallback: dùng BeautifulSoup bóc tách trực tiếp từ page_source nếu Selenium gặp lỗi DOM
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            
            # Tìm trong div.page1 trước
            page1_div = soup.select_one("div.page1")
            next_link = None
            if page1_div:
                for a in page1_div.find_all("a"):
                    if "下一章" in a.get_text():
                        next_link = a
                        break
            
            if not next_link:
                # Tìm toàn bộ trang
                for a in soup.find_all("a"):
                    if "下一章" in a.get_text():
                        next_link = a
                        break

            if next_link:
                href = next_link.get("href", "").strip()
                if href:
                    from urllib.parse import urljoin
                    abs_url = urljoin(driver.current_url, href)
                    if "/txt/" in abs_url:
                        return abs_url

            return None
        except Exception as e:
            print(f"\n{Color.RED}[✗] Lỗi khi xác định chương kế tiếp: {e}{Color.RESET}")
            return None

