from abc import ABC, abstractmethod
from typing import Optional, Tuple, Any

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

