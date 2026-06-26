from abc import ABC, abstractmethod
from typing import Optional, Tuple, Any
from dataclasses import dataclass

@dataclass
class BookSearchResult:
    """Kết quả tìm kiếm 1 cuốn truyện."""
    book_id: str          # ID truyện trên site (ví dụ: "47558")
    title: str            # Tên truyện gốc
    author: str           # Tên tác giả
    book_url: str         # URL trang truyện đầy đủ
    status: str = ""      # Trạng thái: "连载中" / "已完结"
    latest_chapter: str = ""  # Tên chương mới nhất (nếu có)
    cover_url: str = ""   # URL ảnh bìa (nếu có)

@dataclass
class ChapterInfo:
    """Thông tin 1 chương trong mục lục."""
    chapter_id: str       # ID chương (ví dụ: "30756382")
    title: str            # Tên chương (ví dụ: "第1章 重生")
    chapter_url: str      # URL đầy đủ tới trang đọc
    index: int            # Thứ tự chương (1-based)

class Color:
    """Mã màu ANSI cho output terminal."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

class BaseSourceParser(ABC):
    @abstractmethod
    def build_chapter_url(self, story_id: int, chapter_id: int) -> str:
        """Tạo URL đầy đủ của chương truyện từ ID truyện và ID chương."""
        pass

    @abstractmethod
    def get_html(
        self,
        driver: Any,
        url: str,
        is_first_request: bool = False
    ) -> Optional[str]:
        """Tải mã nguồn HTML từ URL sử dụng Selenium Driver.

        Args:
            driver: Instance webdriver.Chrome đang dùng.
            url: URL đầy đủ của trang cần tải.
            is_first_request: True nếu đây là request đầu tiên.

        Returns:
            Chuỗi HTML nếu thành công, None nếu thất bại.
        """
        pass

    @abstractmethod
    def parse_chapter(self, html: str) -> Optional[Tuple[str, str, str]]:
        """Phân tích cú pháp HTML và trả về (tên_truyện, tên_chương, nội_dung_làm_sạch).

        Args:
            html: Chuỗi HTML nguồn.

        Returns:
            Tuple (tên_truyện, tên_chương, nội_dung) hoặc None nếu thất bại.
        """
        pass

    @abstractmethod
    def is_valid_response(self, html: str) -> bool:
        """Kiểm tra xem HTML phản hồi có hợp lệ hay không.

        Args:
            html: Chuỗi HTML nguồn.

        Returns:
            True nếu hợp lệ, False nếu không.
        """
        pass

    def get_next_chapter_url(self, driver: Any) -> Optional[str]:
        """Lấy URL của chương tiếp theo từ driver.

        Args:
            driver: Instance webdriver.Chrome đang dùng.

        Returns:
            URL chương tiếp theo hoặc None.
        """
        return None

    def search_book(self, driver: Any, keyword: str) -> list[BookSearchResult]:
        """Tìm kiếm truyện theo từ khóa.
        Subclass override nếu site hỗ trợ search.
        Default: raise NotImplementedError."""
        raise NotImplementedError(
            f"{self.__class__.__name__} không hỗ trợ tìm kiếm theo tên."
        )

    def get_catalog(self, driver: Any, book_url: str) -> list[ChapterInfo]:
        """Lấy mục lục chương từ trang truyện.
        Subclass override nếu site hỗ trợ.
        Default: raise NotImplementedError."""
        raise NotImplementedError(
            f"{self.__class__.__name__} không hỗ trợ lấy mục lục chương."
        )


