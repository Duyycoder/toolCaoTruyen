import re
from typing import List, Callable, Optional, Tuple

def get_sentences(text: str) -> List[str]:
    """
    Tách đoạn văn thành danh sách các câu dựa trên các dấu kết thúc câu phổ biến.
    """
    if not text:
        return []
    # Tách câu bằng các dấu kết thúc tiếng Anh/Việt và tiếng Trung
    sentences = re.split(r'[.!?。！？\n]+', text)
    return [s.strip() for s in sentences if s.strip()]

def get_sentence_count(text: str) -> int:
    """
    Đếm số lượng câu trong đoạn văn.
    """
    return len(get_sentences(text))

def get_context_before(text: str, index: int, size: int) -> str:
    """
    Lấy ngữ cảnh văn bản phía trước vị trí index với độ dài size.
    """
    return text[:index][-size:]

def get_context_after(text: str, index: int, size: int) -> str:
    """
    Lấy ngữ cảnh văn bản phía sau vị trí index với độ dài size.
    """
    return text[index:][:size]

def retry_translate_paragraph(
    orig_p: str,
    reason: str,
    translate_fn: Callable[[str, float, float], str],
    has_chinese_leak_fn: Callable[[str], bool],
    progress_callback: Optional[Callable[[str], None]] = None,
    default_temp: float = 0.1,
    temp_pass2: float = 0.02,
    temp_pass3: float = 0.02
) -> Tuple[str, bool]:
    """
    Thử dịch lại một đoạn văn bị lỗi (chưa dịch, rò rỉ chữ Hán, hoặc thiếu câu) ở Tầng 2.
    """
    preview = orig_p[:30].replace('\n', ' ')
    if progress_callback:
        if reason == "untranslated":
            progress_callback(f"[->] Phát hiện đoạn chưa được dịch hoặc bị rỗng ở Tầng 1. Tiến hành dịch riêng lẻ đoạn: '{preview}...'")
        elif reason == "leak":
            progress_callback(f"[->] Phát hiện rò rỉ chữ Hán ở đoạn: '{preview}...'. Tiến hành dịch vá...")
        elif reason == "content_missing":
            progress_callback(f"[->] Phát hiện thiếu câu ở đoạn: '{preview}...'. Tiến hành dịch vá với cấu hình tăng cường...")
        else:
            progress_callback(f"[->] Tiến hành dịch vá đoạn ({reason}): '{preview}...'")

    orig_sentences = get_sentence_count(orig_p)

    # Lượt 1: Thử dịch với nhiệt độ thấp (temp_pass2)
    try:
        translated = translate_fn(orig_p, temp_pass2, 1.0)
        if (translated and 
            translated.strip() and 
            translated != orig_p and 
            not has_chinese_leak_fn(translated) and 
            get_sentence_count(translated) >= orig_sentences):
            if progress_callback:
                progress_callback(f"[✓] Vá thành công ở lượt 1: '{translated[:30].strip()}...'")
            return translated, True
    except Exception as e:
        if progress_callback:
            progress_callback(f"[WARN] Thử lượt 1 thất bại: {e}")

    # Lượt 2: Thử dịch với nhiệt độ temp_pass3 và tăng giới hạn token (1.5x)
    try:
        translated = translate_fn(orig_p, temp_pass3, 1.5)
        if (translated and 
            translated.strip() and 
            translated != orig_p and 
            not has_chinese_leak_fn(translated) and 
            get_sentence_count(translated) >= orig_sentences):
            if progress_callback:
                progress_callback(f"[✓] Vá thành công ở lượt 2: '{translated[:30].strip()}...'")
            return translated, True
    except Exception as e:
        if progress_callback:
            progress_callback(f"[WARN] Thử lượt 2 thất bại: {e}")

    # Lượt 3: Thử dịch với nhiệt độ temp_pass3, tăng giới hạn token (2.0x) và nới lỏng điều kiện số lượng câu
    try:
        translated = translate_fn(orig_p, temp_pass3, 2.0)
        if (translated and 
            translated.strip() and 
            translated != orig_p and 
            not has_chinese_leak_fn(translated)):
            if progress_callback:
                progress_callback(f"[✓] Vá thành công ở lượt 3: '{translated[:30].strip()}...'")
            return translated, True
    except Exception as e:
        if progress_callback:
            progress_callback(f"[WARN] Thử lượt 3 thất bại: {e}")

    if progress_callback:
        progress_callback(f"[WARN] Vá thất bại hoàn toàn đoạn: '{preview}...'")
    return orig_p, False
