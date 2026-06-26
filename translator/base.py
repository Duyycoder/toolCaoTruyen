from typing import Callable, Optional

class TranslatorEngine:
    def __init__(self):
        self.glossary = {}
        self.common_idioms = {}
        self.genre = "tien_hiep"

    def set_glossary(self, glossary: dict):
        """
        Nạp từ điển (Global + Per-story) vào engine để ép model sử dụng.
        """
        self.glossary = glossary

    def set_common_idioms(self, common_idioms: dict):
        """
        Nạp từ điển thành ngữ hệ thống vào engine.
        """
        self.common_idioms = common_idioms

    def set_genre(self, genre: str):
        """
        Thiết lập thể loại bối cảnh truyện để định hướng prompt.
        """
        self.genre = genre

    def translate(self, text: str, progress_callback: Optional[Callable[[str], None]] = None) -> str:
        """
        Translate the input text and return the translated string.
        """
        raise NotImplementedError()

    def translate_file(self, input_path: str, output_path: str, progress_callback: Optional[Callable[[str], None]] = None) -> None:
        """
        Read a file, translate its content, and write the result to output_path.
        """
        raise NotImplementedError()

    def extract_glossary_from_text(self, text: str, current_glossary: dict) -> dict:
        """
        Phân tích văn bản, trích xuất các danh từ riêng mới chưa có trong current_glossary.
        Trả về dictionary: {"Chữ Hán": "Bản dịch Hán Việt"}.
        """
        raise NotImplementedError()

    def is_available(self) -> bool:
        """
        Check if the engine (and specifically the selected model/API) is available.
        """
        raise NotImplementedError()
