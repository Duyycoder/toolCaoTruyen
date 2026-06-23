from typing import Callable, Optional

class TranslatorEngine:
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

    def is_available(self) -> bool:
        """
        Check if the engine (and specifically the selected model/API) is available.
        """
        raise NotImplementedError()
