import time
import random
import re
from typing import Optional, Tuple, Any
from bs4 import BeautifulSoup
from sources.base import BaseSourceParser, Color, BookSearchResult, ChapterInfo

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

    def _wait_cloudflare(self, driver: Any, max_wait: int = 30) -> bool:
        """Chờ Cloudflare challenge pass."""
        for i in range(max_wait):
            title = driver.title or ""
            if "Just a moment" in title:
                time.sleep(1)
                continue
            if title and "Just a moment" not in title:
                return True
            time.sleep(0.5)
        return "Just a moment" not in (driver.title or "")

    def _search_via_ddg(self, keyword: str) -> list[BookSearchResult]:
        """Tìm kiếm truyện qua DuckDuckGo HTML search (nhanh, không dính Cloudflare)."""
        import urllib.request
        import urllib.parse
        from bs4 import BeautifulSoup
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.base_url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            home_url = f"{parsed.scheme}://{parsed.netloc}"
            
            query = f"site:{domain} {keyword}"
            url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
            
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                }
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode("utf-8")
                
            soup = BeautifulSoup(html, "html.parser")
            results = []
            seen_ids = set()
            
            for a in soup.find_all("a", class_="result__url"):
                href = a.get("href", "").strip()
                # Giải mã URL redirect từ DuckDuckGo
                match = re.search(r'uddg=([^&]+)', href)
                if match:
                    actual_url = urllib.parse.unquote(match.group(1))
                else:
                    actual_url = a.get_text(strip=True)
                    
                # Chỉ lấy các link chính của truyện trên 69shuba
                if "69shuba" not in actual_url or "/txt/" in actual_url:
                    continue
                    
                book_id_match = re.search(r'/book/(\d+)', actual_url) or re.search(r'69shuba\.com/(\d+)/?$', actual_url)
                if not book_id_match:
                    continue
                    
                book_id = book_id_match.group(1)
                if book_id in seen_ids:
                    continue
                seen_ids.add(book_id)
                
                title_tag = a.find_previous("a", class_="result__a")
                title = "Unknown"
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    title = re.sub(r'最新章节.*$', '', title)
                    title = re.sub(r'无弹窗.*$', '', title)
                    title = re.sub(r'-69书吧.*$', '', title)
                    title = re.sub(r'[_,\s]+$', '', title)
                    title = title.strip()
                
                results.append(BookSearchResult(
                    book_id=book_id,
                    title=title,
                    author="Unknown",
                    book_url=f"{home_url}/book/{book_id}.htm",
                    status="",
                    latest_chapter=""
                ))
            return results
        except Exception as e:
            print(f"{Color.YELLOW}[WARN] Lỗi tìm kiếm qua DuckDuckGo: {e}. Đang thử công cụ khác...{Color.RESET}")
            return []

    def _search_via_yahoo(self, keyword: str) -> list[BookSearchResult]:
        """Tìm kiếm truyện qua Yahoo Search (không lo CAPTCHA)."""
        import urllib.request
        import urllib.parse
        from bs4 import BeautifulSoup
        
        try:
            from urllib.parse import urlparse, unquote
            parsed = urlparse(self.base_url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            home_url = f"{parsed.scheme}://{parsed.netloc}"
            
            query = f"site:{domain} {keyword}"
            url = "https://search.yahoo.com/search?p=" + urllib.parse.quote(query)
            
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                }
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode("utf-8")
                
            soup = BeautifulSoup(html, "html.parser")
            results = []
            seen_ids = set()
            
            items = soup.select(".algo-title, .compTitle h3 a, #web a")
            
            for a in items:
                href = a.get("href", "").strip()
                if not href:
                    continue
                
                match = re.search(r'/RU=([^/&]+)', href)
                if match:
                    actual_url = unquote(match.group(1))
                else:
                    actual_url = href
                    
                if "69shuba" not in actual_url or "/txt/" in actual_url:
                    continue
                    
                book_id_match = re.search(r'/book/(\d+)', actual_url) or re.search(r'69shuba\.com/(\d+)/?$', actual_url)
                if not book_id_match:
                    continue
                    
                book_id = book_id_match.group(1)
                if book_id in seen_ids:
                    continue
                seen_ids.add(book_id)
                
                title = a.get_text(strip=True)
                title = re.sub(r'^.*?[›»]\s*(?:book\s*[›»]\s*)?\d*', '', title)
                title = re.sub(r'^69shuba\.com', '', title)
                title = re.sub(r'^https?://\S+', '', title)
                title = re.sub(r'最新章节.*$', '', title)
                title = re.sub(r'无弹窗.*$', '', title)
                title = re.sub(r'-69书吧.*$', '', title)
                title = re.sub(r'[_,\s]+$', '', title)
                title = title.strip()
                
                results.append(BookSearchResult(
                    book_id=book_id,
                    title=title,
                    author="Unknown",
                    book_url=f"{home_url}/book/{book_id}.htm",
                    status="",
                    latest_chapter=""
                ))
            return results
        except Exception as e:
            print(f"{Color.YELLOW}[WARN] Lỗi tìm kiếm qua Yahoo: {e}. Đang chuyển sang Selenium...{Color.RESET}")
            return []

    def search_book(self, driver: Any, keyword: str) -> list[BookSearchResult]:
        """Tìm kiếm truyện theo từ khóa, ưu tiên DuckDuckGo -> Yahoo, fallback sang Selenium POST form."""
        # 1. Thử tìm nhanh qua DuckDuckGo để tránh Cloudflare Turnstile
        ddg_results = self._search_via_ddg(keyword)
        if ddg_results:
            return ddg_results
            
        # 2. Thử tìm qua Yahoo Search
        yahoo_results = self._search_via_yahoo(keyword)
        if yahoo_results:
            return yahoo_results
            
        # 3. Nếu các công cụ tìm kiếm khác đều thất bại, chạy Selenium POST form
        from urllib.parse import urlparse
        try:
            parsed = urlparse(self.base_url)
            home_url = f"{parsed.scheme}://{parsed.netloc}"
            
            driver.get(home_url)
            self._wait_cloudflare(driver, max_wait=30)
            
            driver.execute_script('''
                var form = document.createElement('form');
                form.method = 'POST';
                form.action = '/modules/article/search.php';
                var input = document.createElement('input');
                input.name = 'searchkey';
                input.value = arguments[0];
                form.appendChild(input);
                var input2 = document.createElement('input');
                input2.name = 'searchtype';
                input2.value = 'all';
                form.appendChild(input2);
                document.body.appendChild(form);
                form.submit();
            ''', keyword)
            
            self._wait_cloudflare(driver, max_wait=30)
            
            current_url = driver.current_url
            if "/book/" in current_url:
                html = driver.page_source
                soup = BeautifulSoup(html, "html.parser")
                
                title = "Unknown"
                author = "Unknown"
                
                title_el = soup.select_one("div.booknav2 h1 a, div.booknav2 h1, h1")
                if title_el:
                    title = title_el.get_text(strip=True)
                
                author_el = soup.select_one("div.booknav2 p a, div.booknav2 p, p.author")
                if author_el:
                    author_text = author_el.get_text(strip=True)
                    author = author_text.replace("作者：", "").strip()
                    
                book_id_match = re.search(r'/book/(\d+)', current_url)
                if book_id_match:
                    book_id = book_id_match.group(1)
                    book_url = f"{home_url}/book/{book_id}.htm"
                    return [BookSearchResult(
                        book_id=book_id,
                        title=title,
                        author=author,
                        book_url=book_url,
                        status="",
                        latest_chapter="",
                    )]
            
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            results = []
            
            items = soup.select("div.newbox > ul > li")
            if not items:
                items = soup.select("div.newbox ul li")
            
            if items:
                for item in items:
                    title_a = item.select_one("h3 a, a.bookname, h3 > a")
                    if not title_a:
                        continue
                    href = title_a.get("href", "")
                    title = title_a.get_text(strip=True)
                    
                    author_el = item.select_one("div.btm a, .author, span.author")
                    author = author_el.get_text(strip=True) if author_el else "Unknown"
                    
                    status_el = item.select_one(".status, span.status")
                    status = status_el.get_text(strip=True) if status_el else ""
                    
                    book_id_match = re.search(r'/book/(\d+)', href)
                    if book_id_match:
                        book_id = book_id_match.group(1)
                        book_url = f"{home_url}/book/{book_id}.htm"
                        results.append(BookSearchResult(
                            book_id=book_id,
                            title=title,
                            author=author,
                            book_url=book_url,
                            status=status
                        ))
            
            if not results:
                rows = soup.select("table.grid tr")
                for row in rows[1:]:
                    cols = row.select("td")
                    if len(cols) >= 2:
                        title_a = cols[0].select_one("a")
                        if title_a:
                            href = title_a.get("href", "")
                            title = title_a.get_text(strip=True)
                            author = cols[2].get_text(strip=True) if len(cols) > 2 else "Unknown"
                            
                            book_id_match = re.search(r'/book/(\d+)', href)
                            if book_id_match:
                                book_id = book_id_match.group(1)
                                book_url = f"{home_url}/book/{book_id}.htm"
                                results.append(BookSearchResult(
                                    book_id=book_id,
                                    title=title,
                                    author=author,
                                    book_url=book_url,
                                    status=""
                                ))
                                
            if not results:
                items = soup.select(".booklist .bookinfo, .booklist li, .book-item")
                for item in items:
                    title_a = item.select_one("a.bookname, h4 a, .title a, a")
                    if not title_a:
                        continue
                    href = title_a.get("href", "")
                    title = title_a.get_text(strip=True)
                    
                    author_el = item.select_one(".author, span")
                    author = author_el.get_text(strip=True) if author_el else "Unknown"
                    
                    book_id_match = re.search(r'/book/(\d+)', href)
                    if book_id_match:
                        book_id = book_id_match.group(1)
                        book_url = f"{home_url}/book/{book_id}.htm"
                        results.append(BookSearchResult(
                            book_id=book_id,
                            title=title,
                            author=author,
                            book_url=book_url,
                            status=""
                        ))
            
            seen_book_ids = set()
            unique_results = []
            for r in results:
                if r.book_id not in seen_book_ids:
                    seen_book_ids.add(r.book_id)
                    unique_results.append(r)
                    
            return unique_results[:20]
        except Exception as e:
            print(f"{Color.RED}[✗] Lỗi khi tìm kiếm truyện qua Selenium: {e}{Color.RESET}")
            return []

    def get_catalog(self, driver: Any, book_url: str) -> list[ChapterInfo]:
        """Lấy mục lục chương từ trang truyện."""
        from urllib.parse import urljoin, urlparse
        try:
            driver.get(book_url)
            self._wait_cloudflare(driver, max_wait=30)
            
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            
            catalog_selectors = [
                ".catalog > ul > li > a",
                ".catalog ul li a",
                "#catalog li a",
                ".mulu_list li a",
                ".mu_contain ul li a",
                ".listmain dd a"
            ]
            
            chapter_links = []
            for selector in catalog_selectors:
                found = soup.select(selector)
                if found and len(found) >= 5:
                    chapter_links = found
                    break
                    
            # Fallback: nếu không thấy catalog, thử URL /{book_id}/
            if not chapter_links:
                book_id_match = re.search(r'/book/(\d+)', book_url)
                if book_id_match:
                    book_id = book_id_match.group(1)
                    parsed = urlparse(book_url)
                    alt_catalog_url = f"{parsed.scheme}://{parsed.netloc}/{book_id}/"
                    driver.get(alt_catalog_url)
                    self._wait_cloudflare(driver, max_wait=15)
                    html = driver.page_source
                    soup = BeautifulSoup(html, "html.parser")
                    
                    for selector in catalog_selectors:
                        found = soup.select(selector)
                        if found and len(found) >= 5:
                            chapter_links = found
                            break
                            
            if not chapter_links:
                return []
                
            chapters = []
            seen_ids = set()
            index = 0
            
            for a_tag in chapter_links:
                href = a_tag.get("href", "").strip()
                title = a_tag.get_text(strip=True)
                if not href or not title:
                    continue
                    
                chapter_url = urljoin(book_url, href)
                if "/txt/" not in chapter_url:
                    continue
                    
                id_match = re.search(r'/txt/\d+/(\d+)', chapter_url)
                if not id_match:
                    continue
                    
                chapter_id = id_match.group(1)
                if chapter_id in seen_ids:
                    continue
                seen_ids.add(chapter_id)
                
                index += 1
                chapters.append(ChapterInfo(
                    chapter_id=chapter_id,
                    title=title,
                    chapter_url=chapter_url,
                    index=index
                ))
                
            # Kiểm tra thứ tự ngược (mới nhất ở đầu)
            if len(chapters) >= 2:
                try:
                    first_id = int(chapters[0].chapter_id)
                    last_id = int(chapters[-1].chapter_id)
                    if first_id > last_id:
                        chapters.reverse()
                        for i, ch in enumerate(chapters, 1):
                            ch.index = i
                except ValueError:
                    pass
                    
            return chapters
        except Exception as e:
            print(f"{Color.RED}[✗] Lỗi khi lấy mục lục: {e}{Color.RESET}")
            return []


