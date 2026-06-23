import os
import re
import time
import json
import urllib.request
import urllib.error
from typing import List, Callable, Optional
from .base import TranslatorEngine

class GeminiSafetyBlockError(Exception):
    pass

class GeminiTranslator(TranslatorEngine):
    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-2.5-flash",
        temperature: float = 0.2,
        max_chunk_chars: int = 1000,
        leak_threshold_percent: float = 10.0
    ):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_chunk_chars = max_chunk_chars
        self.leak_threshold_ratio = leak_threshold_percent / 100.0
        self.chinese_char_pattern = re.compile(r"[\u4e00-\u9fff]")
        self.last_request_time = 0.0

    def is_available(self) -> bool:
        """
        Kiểm tra xem API Key của Gemini đã được cấu hình hay chưa.
        """
        return bool(self.api_key and self.api_key.strip())

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

    def _execute_api_call(self, url: str, payload: dict) -> str:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=90) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                # Kiểm tra finishReason
                finish_reason = candidates[0].get("finishReason", "")
                if finish_reason in ("SAFETY", "PROHIBITED_CONTENT"):
                    raise GeminiSafetyBlockError("Nội dung bị Gemini từ chối do chính sách an toàn")
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
            
            prompt_feedback = res_data.get("promptFeedback", {})
            if prompt_feedback and prompt_feedback.get("blockReason"):
                raise GeminiSafetyBlockError(f"Nội dung bị Gemini từ chối do chính sách an toàn ({prompt_feedback.get('blockReason')})")
            raise ValueError(f"Gemini API trả về kết quả trống: {res_data}")

    def call_gemini_api(self, text: str, is_title: bool = False, source_lang: str = "zh", progress_callback: Optional[Callable[[str], None]] = None) -> str:
        """
        Gọi API Gemini v1beta để sinh bản dịch với cơ chế tự động thử lại nếu gặp lỗi 429/503.
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
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }

        max_retries = 3
        backoff_seconds = [6, 12, 24]

        for attempt in range(max_retries + 1):
            # Enforce request spacing delay (at least 5.0 seconds between consecutive requests)
            elapsed = time.time() - self.last_request_time
            if elapsed < 5.0:
                time.sleep(5.0 - elapsed)
            self.last_request_time = time.time()

            try:
                return self._execute_api_call(url, payload)
            except urllib.error.HTTPError as e:
                # 1. Lỗi 400 (Bad Request): parse error.message từ response
                if e.code == 400:
                    try:
                        err_body = e.read().decode("utf-8")
                        err_json = json.loads(err_body)
                        err_msg = err_json.get("error", {}).get("message", "Unknown Bad Request")
                    except Exception:
                        err_msg = "Unknown Bad Request"
                    raise ValueError(f"Lỗi định dạng yêu cầu gửi tới Gemini: {err_msg}")
                
                # 2. Lỗi 429 (Rate Limit) hoặc 503 (High Demand/Unavailable)
                if e.code in (429, 503) and attempt < max_retries:
                    wait_time = backoff_seconds[attempt]
                    # Trích xuất thời gian chờ từ header "Retry-After" nếu có
                    retry_after = e.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_time = int(retry_after)
                    
                    log_msg = f"[WARN] Đã vượt giới hạn tốc độ miễn phí, đang chờ {wait_time}s để thử lại..."
                    if progress_callback:
                        progress_callback(log_msg)
                    else:
                        print(log_msg)
                    
                    time.sleep(wait_time)
                    continue

                try:
                    err_body = e.read().decode("utf-8")
                except Exception:
                    err_body = str(e)
                raise ValueError(f"Lỗi HTTP {e.code} từ Gemini API: {err_body}")
            except Exception as e:
                if isinstance(e, GeminiSafetyBlockError):
                    raise e
                if isinstance(e, ValueError) and "Lỗi định dạng yêu cầu" in str(e):
                    raise e
                # Các lỗi kết nối khác
                if attempt < max_retries:
                    wait_time = backoff_seconds[attempt]
                    log_msg = f"[WARN] Lỗi kết nối ({e}), đang chờ {wait_time}s để thử lại..."
                    if progress_callback:
                        progress_callback(log_msg)
                    else:
                        print(log_msg)
                    time.sleep(wait_time)
                    continue
                raise e

    def translate_chunk_with_retry(self, chunk: str, chunk_index: int, total_chunks: int, progress_callback: Optional[Callable[[str], None]] = None, source_lang: str = "zh") -> str:
        """
        Dịch một chunk văn bản, thử lại tối đa 1 lần nếu phát hiện rò rỉ chữ Trung Quốc vượt ngưỡng.
        """
        output = self.call_gemini_api(chunk, source_lang=source_lang, progress_callback=progress_callback)
        
        if self.contains_chinese_leak(output):
            warn_msg = f"[WARN] Phát hiện rò rỉ chữ Trung ở chunk {chunk_index} ({len(self.chinese_char_pattern.findall(output))} ký tự). Tiến hành dịch lại ở nhiệt độ thấp hơn..."
            if progress_callback:
                progress_callback(warn_msg)
            
            original_temp = self.temperature
            self.temperature = 0.05
            try:
                output = self.call_gemini_api(chunk, source_lang=source_lang, progress_callback=progress_callback)
            finally:
                self.temperature = original_temp

        return output

    def _get_ollama_fallback_translator(self) -> Optional[TranslatorEngine]:
        try:
            from core.config_manager import load_config
            from .ollama_translator import OllamaTranslator
            config = load_config()
            if config and "translator" in config:
                ollama_model = config["translator"].get("ollama_model", "qwen2.5:7b-instruct")
                leak_threshold = config["translator"].get("leak_threshold_percent", 10)
                return OllamaTranslator(
                    model=ollama_model,
                    leak_threshold_percent=leak_threshold
                )
        except Exception:
            pass
        return None

    def translate(self, text: str, progress_callback: Optional[Callable[[str], None]] = None, source_lang: str = "zh") -> str:
        """
        Dịch toàn bộ văn bản (bao gồm tiêu đề và thân bài) sử dụng cơ chế chunking 2 tầng tương tự Ollama.
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
                translated_title = self.call_gemini_api(title_line, is_title=True, source_lang=source_lang, progress_callback=progress_callback)
            except GeminiSafetyBlockError:
                if progress_callback:
                    progress_callback("[INFO] Gemini từ chối dịch tiêu đề do chính sách nội dung, đang chuyển sang dịch bằng Ollama (local)...")
                try:
                    ollama_trans = self._get_ollama_fallback_translator()
                    if ollama_trans and ollama_trans.is_available():
                        translated_title = ollama_trans.translate(title_line, progress_callback=progress_callback, source_lang=source_lang)
                    else:
                        raise ValueError("Ollama không khả dụng để fallback (chưa chạy hoặc thiếu model)")
                except Exception as ollama_err:
                    translated_title = title_line
                    if progress_callback:
                        progress_callback(f"[WARN] Fallback sang Ollama thất bại: {ollama_err}. Giữ nguyên gốc.")
            except Exception as e:
                translated_title = title_line
                if progress_callback:
                    progress_callback(f"[WARN] Lỗi dịch tiêu đề: {e}. Giữ nguyên gốc.")

        if progress_callback:
            progress_callback("[->] Đang gửi nội dung tới Gemini API...")

        chunks = self.split_text_into_chunks(body_text)
        total_chunks = len(chunks)
        paragraph_mappings = []

        # Tầng 1: Dịch từng chunk (có retry)
        for i, chunk in enumerate(chunks, 1):
            orig_paras = [p.strip() for p in chunk.split("\n\n") if p.strip()]
            if progress_callback and total_chunks > 1:
                progress_callback(f"[->] Đang dịch phần {i}/{total_chunks}...")
            
            try:
                translated_chunk = self.translate_chunk_with_retry(
                    chunk, i, total_chunks, progress_callback, source_lang=source_lang
                )
            except GeminiSafetyBlockError:
                if progress_callback:
                    progress_callback(f"[INFO] Gemini từ chối dịch phần {i} do chính sách nội dung, đang chuyển sang dịch bằng Ollama (local) cho đoạn này...")
                try:
                    ollama_trans = self._get_ollama_fallback_translator()
                    if ollama_trans and ollama_trans.is_available():
                        translated_chunk = ollama_trans.translate(chunk, progress_callback=progress_callback, source_lang=source_lang)
                    else:
                        raise ValueError("Ollama không khả dụng để fallback (chưa chạy hoặc thiếu model)")
                except Exception as ollama_err:
                    if progress_callback:
                        progress_callback(f"[WARN] Fallback sang Ollama thất bại: {ollama_err}. Giữ nguyên bản gốc để vá ở Tầng 2.")
                    translated_chunk = chunk
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
            if orig_p == trans_p:
                # Nếu đoạn dịch giống hệt đoạn gốc (chưa được dịch tí nào do lỗi cả chunk ở Tầng 1),
                # thử dịch lại bằng Ollama
                if progress_callback:
                    progress_callback(f"[INFO] Phát hiện đoạn chưa được dịch ở Tầng 1. Tiến hành dịch bằng Ollama...")
                try:
                    ollama_trans = self._get_ollama_fallback_translator()
                    if ollama_trans and ollama_trans.is_available():
                        re_trans = ollama_trans.translate(orig_p, progress_callback=progress_callback, source_lang=source_lang)
                    else:
                        raise ValueError("Ollama không khả dụng để fallback")
                except Exception:
                    re_trans = orig_p

                if re_trans == orig_p or self.contains_chinese_leak(re_trans):
                    failed_count += 1
                    repaired_paras.append(f"> ⚠️ [Đoạn này AI dịch không thành công, giữ nguyên bản gốc]\n\n{orig_p}")
                else:
                    repaired_paras.append(re_trans)
            elif self.contains_chinese_leak(trans_p):
                if progress_callback:
                    progress_callback(f"[->] Phát hiện rò rỉ chữ Hán ở đoạn: '{trans_p[:30]}...'. Tiến hành dịch vá...")
                
                try:
                    re_trans = self.call_gemini_api(orig_p, source_lang=source_lang, progress_callback=progress_callback)
                    if self.contains_chinese_leak(re_trans):
                        original_temp = self.temperature
                        self.temperature = 0.05
                        try:
                            re_trans = self.call_gemini_api(orig_p, source_lang=source_lang, progress_callback=progress_callback)
                        finally:
                            self.temperature = original_temp
                except GeminiSafetyBlockError:
                    if progress_callback:
                        progress_callback(f"[INFO] Gemini từ chối vá đoạn do chính sách nội dung, đang chuyển sang vá bằng Ollama...")
                    try:
                        ollama_trans = self._get_ollama_fallback_translator()
                        if ollama_trans and ollama_trans.is_available():
                            re_trans = ollama_trans.translate(orig_p, progress_callback=progress_callback, source_lang=source_lang)
                        else:
                            raise ValueError("Ollama không khả dụng để fallback")
                    except Exception as ollama_err:
                        re_trans = orig_p
                        if progress_callback:
                            progress_callback(f"[WARN] Fallback sang Ollama thất bại: {ollama_err}")
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
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Không tìm thấy file nguồn: {input_path}")

        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()

        translated_text = self.translate(text, progress_callback, source_lang)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(translated_text)
