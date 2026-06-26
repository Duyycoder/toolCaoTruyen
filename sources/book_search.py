"""
sources/book_search.py
Module điều phối tìm kiếm truyện và lấy mục lục.
"""
from typing import Optional, List
from sources.base import BaseSourceParser, BookSearchResult, ChapterInfo, Color


class BookSearcher:
    """Điều phối tìm kiếm truyện và lấy mục lục.
    Quản lý Selenium driver riêng cho thao tác search/catalog.
    
    Usage:
        with BookSearcher(parser) as searcher:
            results = searcher.search("游戏修仙")
            if results:
                catalog = searcher.get_catalog(results[0].book_url)
    
    Driver lifecycle:
    - Lazy init: driver chỉ tạo khi cần (lần đầu gọi search/get_catalog)
    - Reuse: cùng 1 driver dùng cho cả search + catalog
    - Auto-close: context manager __exit__() tự đóng driver
    """
    
    def __init__(self, parser: BaseSourceParser):
        self.parser = parser
        self._driver = None  # Lazy init
    
    def _ensure_driver(self):
        """Lazy init: chỉ mở Chrome khi thực sự cần.
        
        Gọi create_browser() từ crawler_engine.py 
        (cùng config chống bot, off-screen, v.v.)
        """
        if self._driver is None:
            from core.crawler_engine import create_browser
            self._driver = create_browser()
    
    def search(self, keyword: str) -> List[BookSearchResult]:
        """Tìm kiếm truyện theo tên.
        
        Args:
            keyword: Tên truyện (tiếng Trung)
        
        Returns:
            list[BookSearchResult] — rỗng nếu không tìm thấy
        """
        self._ensure_driver()
        try:
            return self.parser.search_book(self._driver, keyword)
        except NotImplementedError:
            print(f"{Color.RED}[✗] Nguồn truyện này không hỗ trợ "
                  f"tìm kiếm.{Color.RESET}")
            return []
        except Exception as e:
            print(f"{Color.RED}[✗] Lỗi tìm kiếm: {e}{Color.RESET}")
            return []
    
    def get_catalog(self, book_url: str) -> List[ChapterInfo]:
        """Lấy mục lục chương.
        
        Args:
            book_url: URL trang truyện (ví dụ: https://www.69shuba.com/book/47558.htm)
        
        Returns:
            list[ChapterInfo] — rỗng nếu không lấy được
        """
        self._ensure_driver()
        try:
            return self.parser.get_catalog(self._driver, book_url)
        except NotImplementedError:
            print(f"{Color.RED}[✗] Nguồn truyện này không hỗ trợ "
                  f"lấy mục lục.{Color.RESET}")
            return []
        except Exception as e:
            print(f"{Color.RED}[✗] Lỗi lấy mục lục: {e}{Color.RESET}")
            return []
    
    def close(self):
        """Đóng Selenium driver. 
        LUÔN gọi khi xong — hoặc dùng context manager."""
        if self._driver:
            try:
                self._driver.quit()
                print(f"{Color.DIM}[i] Đã đóng trình duyệt "
                      f"tìm kiếm.{Color.RESET}")
            except Exception:
                pass
            self._driver = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False  # Không nuốt exception
