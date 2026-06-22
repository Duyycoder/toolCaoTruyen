import os
import re
import time
import json
import urllib.request
from typing import List, Callable, Optional
from .base import TranslatorEngine

class OllamaTranslator(TranslatorEngine):
    def __init__(
        self,
        model: str = "qwen2.5:7b-instruct",
        api_url: str = "http://localhost:11434/api/chat",
        num_ctx: int = 4096,
        temperature: float = 0.1,
        max_chunk_chars: int = 350,  # Benchmark optimal size
        leak_threshold_percent: float = 10.0
    ):
        self.model = model
        self.api_url = api_url
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.max_chunk_chars = max_chunk_chars
        self.leak_threshold_ratio = leak_threshold_percent / 100.0
        self.chinese_char_pattern = re.compile(r"[\u4e00-\u9fff]")

    def is_available(self) -> bool:
        """
        Kiểm tra xem model đang chọn có tồn tại trong danh sách tags của Ollama hay không.
        """
        tags_url = self.api_url.replace("/api/chat", "/api/tags")
        try:
            req = urllib.request.Request(tags_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                
                if self.model in models:
                    return True
                
                model_base = self.model.split(":")[0]
                for m in models:
                    if m == self.model or m.split(":")[0] == model_base:
                        return True
                return False
        except Exception:
            return False

    def split_text_into_chunks(self, text: str) -> List[str]:
        """
        Chia văn bản thành các chunk nhỏ hơn dựa trên ranh giới đoạn văn (\n\n).
        """
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para_len = len(para)
            if not para.strip():
                continue
            
            if para_len > self.max_chunk_chars:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_length = 0
                chunks.append(para)
                continue

            if current_length + para_len + 2 > self.max_chunk_chars:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_length = para_len
            else:
                current_chunk.append(para)
                current_length += para_len + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def contains_chinese_leak(self, text: str, threshold_ratio: Optional[float] = None, min_chars: int = 5) -> bool:
        """
        Kiểm tra xem bản dịch có bị rò rỉ ký tự tiếng Trung hay không.
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

    def call_ollama_api(self, text: str, is_title: bool = False, source_lang: str = "zh") -> str:
        """
        Gọi API Ollama Chat để dịch văn bản.
        """
        system_instruction = self.build_system_prompt(source_lang, is_title)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": text}
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "top_p": 0.9,
                "num_ctx": self.num_ctx,
                "num_predict": 1024
            }
        }

        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=90) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("message", {}).get("content", "").strip()

    def translate_chunk_with_retry(self, chunk: str, chunk_index: int, total_chunks: int, progress_callback: Optional[Callable[[str], None]] = None, source_lang: str = "zh") -> str:
        """
        Dịch một chunk văn bản, thử lại tối đa 1 lần nếu phát hiện rò rỉ chữ Trung Quốc vượt ngưỡng.
        """
        output = self.call_ollama_api(chunk, source_lang=source_lang)
        
        if self.contains_chinese_leak(output):
            warn_msg = f"[WARN] Phát hiện rò rỉ chữ Trung ở chunk {chunk_index} ({len(self.chinese_char_pattern.findall(output))} ký tự). Tiến hành dịch lại ở nhiệt độ thấp hơn..."
            if progress_callback:
                progress_callback(warn_msg)
            
            # Thử lại lượt 2 với temperature thấp hơn để tăng tính tuân thủ
            original_temp = self.temperature
            self.temperature = 0.02
            try:
                output = self.call_ollama_api(chunk, source_lang=source_lang)
            finally:
                self.temperature = original_temp

        return output

    def translate(self, text: str, progress_callback: Optional[Callable[[str], None]] = None, source_lang: str = "zh") -> str:
        """
        Dịch toàn bộ văn bản (bao gồm tiêu đề và thân bài) sử dụng cơ chế chunking 2 tầng.
        """
        if not self.is_available():
            err_msg = f"Model {self.model} chưa được tải. Vui lòng chạy lệnh: `ollama pull {self.model}`"
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
                progress_callback("[->] Đang dịch tiêu đề chương...")
            try:
                translated_title = self.call_ollama_api(title_line, is_title=True, source_lang=source_lang)
            except Exception as e:
                translated_title = title_line
                if progress_callback:
                    progress_callback(f"[WARN] Lỗi dịch tiêu đề: {e}. Giữ nguyên gốc.")

        chunks = self.split_text_into_chunks(body_text)
        total_chunks = len(chunks)
        paragraph_mappings = []

        # Tầng 1: Dịch từng chunk (có retry)
        for i, chunk in enumerate(chunks, 1):
            orig_paras = [p.strip() for p in chunk.split("\n\n") if p.strip()]
            
            try:
                translated_chunk = self.translate_chunk_with_retry(
                    chunk, i, total_chunks, progress_callback, source_lang=source_lang
                )
            except Exception as e:
                if progress_callback:
                    progress_callback(f"[WARN] Lỗi dịch chunk {i}: {e}. Giữ nguyên bản gốc để vá ở Tầng 2.")
                translated_chunk = chunk

            trans_paras = [p.strip() for p in translated_chunk.split("\n\n") if p.strip()]
            
            if len(orig_paras) == len(trans_paras):
                paragraph_mappings.extend(list(zip(orig_paras, trans_paras)))
            else:
                paragraph_mappings.append(("\n\n".join(orig_paras), "\n\n".join(trans_paras)))

        # Tầng 2: Quét toàn file sau ghép để vá rò rỉ từng đoạn
        if progress_callback:
            progress_callback("[->] Đang quét lại toàn bộ văn bản (Tầng 2) để sửa lỗi rò rỉ ranh giới...")

        repaired_paras = []
        failed_count = 0

        for orig_p, trans_p in paragraph_mappings:
            if self.contains_chinese_leak(trans_p):
                if progress_callback:
                    progress_callback(f"[->] Phát hiện rò rỉ chữ Hán ở đoạn: '{trans_p[:30]}...'. Tiến hành dịch vá...")
                
                try:
                    re_trans = self.call_ollama_api(orig_p, source_lang=source_lang)
                    if self.contains_chinese_leak(re_trans):
                        # Thử lại lần cuối ở nhiệt độ 0.02
                        original_temp = self.temperature
                        self.temperature = 0.02
                        try:
                            re_trans = self.call_ollama_api(orig_p, source_lang=source_lang)
                        finally:
                            self.temperature = original_temp
                except Exception:
                    re_trans = orig_p
                
                if self.contains_chinese_leak(re_trans):
                    failed_count += 1
                    repaired_paras.append(f"> ⚠️ [Đoạn này AI dịch không thành công, giữ nguyên bản gốc]\n\n{orig_p}")
                    if progress_callback:
                        progress_callback(f"[WARN] Vá thất bại, giữ nguyên bản gốc đoạn: '{orig_p[:30]}...'")
                else:
                    repaired_paras.append(re_trans)
                    if progress_callback:
                        progress_callback(f"[SUCCESS] Vá thành công: '{re_trans[:30]}...'")
            else:
                repaired_paras.append(trans_p)

        translated_body = "\n\n".join(repaired_paras)
        
        total_paras = len(paragraph_mappings)
        success_paras = total_paras - failed_count
        if progress_callback:
            progress_callback(f"[INFO] Hoàn thành dịch: thành công {success_paras}/{total_paras} đoạn, {failed_count} đoạn lỗi.")

        final_output = []
        if translated_title:
            final_output.append(translated_title)
        
        final_output.append(translated_body)
        return "\n\n".join(final_output)

    def translate_file(self, input_path: str, output_path: str, progress_callback: Optional[Callable[[str], None]] = None, source_lang: str = "zh") -> None:
        """
        Đọc một file, dịch nội dung và ghi ra file đích.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Không tìm thấy file nguồn: {input_path}")

        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()

        translated_text = self.translate(text, progress_callback, source_lang)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(translated_text)
