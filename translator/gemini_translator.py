import os
import re
import json
import urllib.request
from typing import Callable, Optional
from .base import TranslatorEngine

class GeminiTranslator(TranslatorEngine):
    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-2.5-flash",
        temperature: float = 0.2,
        leak_threshold_percent: float = 10.0
    ):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.leak_threshold_ratio = leak_threshold_percent / 100.0
        self.chinese_char_pattern = re.compile(r"[\u4e00-\u9fff]")

    def is_available(self) -> bool:
        """
        Kiểm tra xem API Key của Gemini đã được cấu hình hay chưa.
        """
        return bool(self.api_key and self.api_key.strip())

    def contains_chinese_leak(self, text: str, threshold_ratio: Optional[float] = None, min_chars: int = 5) -> bool:
        """
        Kiểm tra rò rỉ chữ Hán trong bản dịch.
        """
        if not text:
            return False
        if threshold_ratio is None:
            threshold_ratio = self.leak_threshold_ratio
            
        chinese_chars = self.chinese_char_pattern.findall(text)
        count = len(chinese_chars)
        if count >= min_chars and (count / len(text)) > threshold_ratio:
            return True
        return False

    def build_system_prompt(self, source_lang: str, is_title: bool = False) -> str:
        """
        Xây dựng prompt chỉ dẫn dịch thuật động theo ngôn ngữ gốc.
        """
        lang_map = {
            "zh": "Chinese",
            "en": "English",
            "ja": "Japanese",
            "ko": "Korean"
        }
        lang_name = lang_map.get(source_lang, "Chinese")
        
        system_instruction = (
            f"You are an expert translator specializing in translating {lang_name} web novels to Vietnamese.\n"
            f"Translate the user's {lang_name} text to Vietnamese.\n"
            "Requirements:\n"
            "1. Translate into natural, smooth, and high-quality Vietnamese (novel style).\n"
            "2. Keep the original Markdown formatting (headings, blank lines) exactly as-is.\n"
            f"3. Translate names consistently (e.g. for Chinese names like 江思 to Giang Tư, 冰糖 to Băng Đường).\n"
            f"4. DO NOT leak or write any original non-Vietnamese characters in your output. Every sentence must be translated into Vietnamese.\n"
            "5. Output ONLY the translated Vietnamese text. Do not add comments, notes, or explanations."
        )
        if is_title:
            system_instruction += "\nNote: This is the chapter title. Keep it short and preserve Markdown heading prefix."
        return system_instruction

    def call_gemini_api(self, text: str, is_title: bool = False, source_lang: str = "zh") -> str:
        """
        Gọi API Gemini v1beta để sinh bản dịch.
        """
        if not self.is_available():
            raise ValueError("Gemini API key chưa được cấu hình.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        system_instruction = self.build_system_prompt(source_lang, is_title)

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": text}
                    ]
                }
            ],
            "systemInstruction": {
                "parts": [
                    {"text": system_instruction}
                ]
            },
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": 4096
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                candidates = res_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
                raise ValueError(f"Gemini API trả về kết quả trống: {res_data}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            raise ValueError(f"Lỗi HTTP {e.code} từ Gemini API: {err_body}")

    def translate(self, text: str, progress_callback: Optional[Callable[[str], None]] = None, source_lang: str = "zh") -> str:
        """
        Dịch toàn bộ văn bản bằng Gemini API.
        """
        if not self.is_available():
            err_msg = "Gemini API Key chưa được cấu hình. Vui lòng nhập API Key trong phần Cấu hình."
            if progress_callback:
                progress_callback(f"[ERROR] {err_msg}")
            raise ValueError(err_msg)

        lines = text.split("\n")
        title_line = ""
        body_text = text

        if lines and lines[0].strip().startswith("#"):
            title_line = lines[0]
            body_text = "\n".join(lines[1:])

        translated_title = ""
        if title_line:
            if progress_callback:
                progress_callback("[->] Đang dịch tiêu đề chương bằng Gemini...")
            try:
                translated_title = self.call_gemini_api(title_line, is_title=True, source_lang=source_lang)
            except Exception as e:
                translated_title = title_line
                if progress_callback:
                    progress_callback(f"[WARN] Lỗi dịch tiêu đề: {e}. Giữ nguyên gốc.")

        if progress_callback:
            progress_callback("[->] Đang gửi nội dung tới Gemini API...")

        # Với Gemini, ta chia chunk lớn hơn (khoảng 4000 ký tự) để đảm bảo không bị quá tải token sinh
        paragraphs = body_text.split("\n\n")
        chunks = []
        current_chunk = []
        current_length = 0
        for para in paragraphs:
            if not para.strip():
                continue
            if current_length + len(para) + 2 > 4000:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_length = len(para)
            else:
                current_chunk.append(para)
                current_length += len(para) + 2
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        translated_chunks = []
        total_chunks = len(chunks)
        failed_count = 0

        for i, chunk in enumerate(chunks, 1):
            if progress_callback and total_chunks > 1:
                progress_callback(f"[->] Đang dịch phần {i}/{total_chunks}...")
            
            try:
                output = self.call_gemini_api(chunk, source_lang=source_lang)
                if self.contains_chinese_leak(output):
                    if progress_callback:
                        progress_callback(f"[WARN] Phát hiện rò rỉ chữ Trung từ Gemini ở phần {i}. Thử dịch lại ở nhiệt độ thấp...")
                    orig_temp = self.temperature
                    self.temperature = 0.05
                    try:
                        output = self.call_gemini_api(chunk, source_lang=source_lang)
                    finally:
                        self.temperature = orig_temp
                
                # Quét và xử lý rò rỉ sau retry
                if self.contains_chinese_leak(output):
                    chunk_orig_paras = [p.strip() for p in chunk.split("\n\n") if p.strip()]
                    chunk_trans_paras = [p.strip() for p in output.split("\n\n") if p.strip()]
                    if len(chunk_orig_paras) == len(chunk_trans_paras):
                        repaired = []
                        for op, tp in zip(chunk_orig_paras, chunk_trans_paras):
                            if self.contains_chinese_leak(tp):
                                repaired.append(f"> ⚠️ [Đoạn này AI dịch không thành công, giữ nguyên bản gốc]\n\n{op}")
                                failed_count += 1
                            else:
                                repaired.append(tp)
                        output = "\n\n".join(repaired)
                    else:
                        failed_count += 1
                        output = f"> ⚠️ [Đoạn này AI dịch không thành công, giữ nguyên bản gốc]\n\n{chunk}"
                
                translated_chunks.append(output)
            except Exception as e:
                failed_count += 1
                if progress_callback:
                    progress_callback(f"[ERROR] Lỗi dịch phần {i}: {e}")
                translated_chunks.append(f"> ⚠️ [Đoạn này AI dịch không thành công, giữ nguyên bản gốc]\n\n{chunk}")

        translated_body = "\n\n".join(translated_chunks)
        
        if progress_callback:
            progress_callback(f"[INFO] Hoàn thành dịch bằng Gemini: dịch xong {total_chunks - failed_count}/{total_chunks} phần.")

        final_output = []
        if translated_title:
            final_output.append(translated_title)
        final_output.append(translated_body)
        return "\n\n".join(final_output)

    def translate_file(self, input_path: str, output_path: str, progress_callback: Optional[Callable[[str], None]] = None, source_lang: str = "zh") -> None:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Không tìm thấy file nguồn: {input_path}")

        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()

        translated_text = self.translate(text, progress_callback, source_lang)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(translated_text)
