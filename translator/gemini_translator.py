import os
import re
import time
import json
import urllib.request
import urllib.error
from typing import List, Callable, Optional
from .base import TranslatorEngine
from .utils import get_sentence_count, get_sentences, get_context_before, get_context_after, retry_translate_paragraph

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
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_chunk_chars = max_chunk_chars
        self.leak_threshold_ratio = leak_threshold_percent / 100.0
        self.chinese_char_pattern = re.compile(r"[\u4e00-\u9fff]")
        self.last_request_time = 0.0
        self.last_finish_reason = None

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
                if current_chunk:
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
        (Cơ chế Zero Tolerance: Chỉ cần 1 ký tự Hán là báo lỗi ngay lập tức)
        """
        if not text:
            return False
            
        chinese_chars = self.chinese_char_pattern.findall(text)
        if len(chinese_chars) > 0:
            return True
        return False

    def has_chinese_leak(self, text: str) -> bool:
        """
        Kiểm tra rò rỉ chữ Hán, có xử lý chống pha loãng đối với văn bản chứa nhiều đoạn (\n\n).
        """
        if not text:
            return False
        if "\n\n" in text:
            sub_paras = [sp.strip() for sp in text.split("\n\n") if sp.strip()]
            for sp in sub_paras:
                if self.contains_chinese_leak(sp):
                    return True
            return False
        return self.contains_chinese_leak(text)

    def build_system_prompt(self, source_lang: str, is_title: bool = False, chunk_text: Optional[str] = None) -> str:
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
            "5. Output ONLY the translated Vietnamese text. Do not add comments, notes, or explanations.\n"
            f"6. If the input contains short questions, dialogues, or specific terms (e.g. '“对抗？”'), translate them fully into Vietnamese (e.g. '“Đối kháng?”') and do not write or copy any original {lang_name} characters in your output."
        )

        active_glossary = {}
        if self.glossary:
            if chunk_text:
                for k, v in self.glossary.items():
                    if k in chunk_text:
                        active_glossary[k] = v
            else:
                active_glossary = self.glossary

        if active_glossary:
            glossary_text = "\n".join([f"- {k} -> {v}" for k, v in active_glossary.items()])
            system_instruction += (
                f"\n\nCRITICAL REQUIREMENT: You MUST strictly use the following Glossary for specific terms and names. "
                f"Do not invent or use other translations for these terms:\n{glossary_text}\n"
            )

        if is_title:
            system_instruction += "\nNote: This is the chapter title. Keep it short and preserve Markdown heading prefix."
        return system_instruction

    def extract_glossary_from_text(self, text: str, current_glossary: dict) -> dict:
        """
        Trích xuất các danh từ riêng MỚI từ văn bản tiếng Trung bằng Gemini API.
        """
        prompt = (
            "Dưới đây là một đoạn truyện chữ (tiên hiệp/đô thị/mạng) tiếng Trung.\n"
            "Nhiệm vụ của bạn là phân tích và lập bảng thuật ngữ dịch thuật (glossary) chuẩn xác nhất để làm dữ liệu dịch sang tiếng Việt.\n"
            "Yêu cầu trích xuất cụ thể:\n"
            "1. Tên nhân vật (Ví dụ: 顾安 -> Cố An, 张春秋 -> Trương Xuân Thu, 姬少玉 -> Cơ Thiếu Ngọc / Cơ Tiêu Ngọc). Đảm bảo xưng hô phù hợp với ngữ cảnh (Ví dụ: 顾安兄弟 -> Huynh đệ Cố An, KHÔNG dịch thành Cố An tỷ đệ).\n"
            "2. Tên địa danh, phòng đường, thung lũng (Ví dụ: 药谷 -> Dược Cốc, 丹药堂 -> Đan Dược Đường, 沧州 -> Thương Châu, 太玄门 -> Thái Huyền Môn). Tránh dịch sang nghĩa thuần Việt sai lệch (Ví dụ: KHÔNG dịch 药谷 thành thung lũng thuốc / dược giá / thuốc thung).\n"
            "3. Thuật ngữ tu tiên, cảnh giới, công pháp, thảo dược (Ví dụ: 筑基 -> Trúc Cơ, 修为 -> Tu vi, 不入流 -> Bất nhập lưu, 一阶 -> Nhất giai, 夺取寿命 -> Đoạt lấy tuổi thọ, 春木功 -> Xuân Mộc Công, 赤灵花 -> Xích Linh Hoa). Tránh dịch sai lệch bản chất tu tiên (Ví dụ: KHÔNG dịch 修为 thành thiên tài, KHÔNG dịch 不入流 thành không đạt tiêu chuẩn, KHÔNG dịch 赤灵花 thành Hồng Linh Hoa).\n"
            "4. Từ lóng mạng và thuật ngữ cốt lõi (Ví dụ: 金手指 -> Ngón tay vàng / Hệ thống hack, KHÔNG dịch thành kim chỉ tay).\n"
        )
        if current_glossary:
            existing_keys = ", ".join(current_glossary.keys())
            prompt += f"\nBỎ QUA và KHÔNG trích xuất lại các từ đã có trong danh sách từ điển hiện tại sau: {existing_keys}.\n"
        
        prompt += (
            "\nTRẢ VỀ DUY NHẤT một chuỗi JSON hợp lệ (không chứa markdown block ```json, chỉ có ngoặc nhọn). "
            "Định dạng JSON: {\"Chữ Hán\": \"Bản dịch Hán Việt hoặc Nghĩa chuẩn tương ứng\"}.\n"
            "Nếu không có từ mới nào đáng chú ý, hãy trả về JSON rỗng: {}\n\n"
            "Đoạn truyện cần trích xuất:\n"
            f"{text[:3000]}"
        )
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": "You are a data extractor. Output ONLY raw JSON."}]},
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }
        
        try:
            res_text = self._execute_api_call(url, payload)
            # Clean up potential markdown
            res_text = res_text.strip()
            if res_text.startswith("```json"): res_text = res_text[7:]
            if res_text.startswith("```"): res_text = res_text[3:]
            if res_text.endswith("```"): res_text = res_text[:-3]
            res_text = res_text.strip()
            
            data = json.loads(res_text)
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"[Warning] Lỗi khi extract glossary (Gemini): {e}")
            
        return {}

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
                self.last_finish_reason = finish_reason
                if finish_reason in ("SAFETY", "PROHIBITED_CONTENT"):
                    raise GeminiSafetyBlockError("Nội dung bị Gemini từ chối do chính sách an toàn")
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
            
            prompt_feedback = res_data.get("promptFeedback", {})
            if prompt_feedback and prompt_feedback.get("blockReason"):
                raise GeminiSafetyBlockError(f"Nội dung bị Gemini từ chối do chính sách an toàn ({prompt_feedback.get('blockReason')})")
            raise ValueError(f"Gemini API trả về kết quả trống: {res_data}")

    def call_gemini_api(self, text: str, is_title: bool = False, source_lang: str = "zh", progress_callback: Optional[Callable[[str], None]] = None, override_max_tokens: Optional[int] = None) -> str:
        """
        Gọi API Gemini v1beta để sinh bản dịch với cơ chế tự động thử lại nếu gặp lỗi 429/503.
        """
        if not self.is_available():
            raise ValueError("Gemini API key chưa được cấu hình.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        system_instruction = self.build_system_prompt(source_lang, is_title, text)

        max_tokens = override_max_tokens if override_max_tokens is not None else 4096

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
                "maxOutputTokens": max_tokens
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
        self.last_finish_reason = None
        output = self.call_gemini_api(chunk, source_lang=source_lang, progress_callback=progress_callback)
        
        # 1. Kiểm tra giới hạn token (MAX_TOKENS)
        if self.last_finish_reason == "MAX_TOKENS":
            warn_msg = f"[WARN] Chunk {chunk_index} bị cắt cụt do giới hạn token Gemini. Đang thử lại với maxOutputTokens lớn hơn..."
            if progress_callback:
                progress_callback(warn_msg)
            
            # Thử lại với 1.5x tokens (tối đa 8192)
            retry_max_tokens = min(8192, int(4096 * 1.5))
            output = self.call_gemini_api(chunk, source_lang=source_lang, progress_callback=progress_callback, override_max_tokens=retry_max_tokens)
            
            if self.last_finish_reason == "MAX_TOKENS":
                raise ValueError("output_truncated")

        # 2. Kiểm tra rò rỉ chữ Trung Quốc
        if self.has_chinese_leak(output):
            warn_msg = f"[WARN] Phát hiện rò rỉ chữ Trung ở chunk {chunk_index} ({len(self.chinese_char_pattern.findall(output))} ký tự). Tiến hành dịch lại ở nhiệt độ thấp hơn..."
            if progress_callback:
                progress_callback(warn_msg)
            
            original_temp = self.temperature
            self.temperature = 0.05
            try:
                output = self.call_gemini_api(chunk, source_lang=source_lang, progress_callback=progress_callback)
                if self.last_finish_reason == "MAX_TOKENS":
                    raise ValueError("output_truncated")
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
            except Exception as e:
                is_safety = isinstance(e, GeminiSafetyBlockError)
                if progress_callback:
                    if is_safety:
                        progress_callback("[INFO] Gemini từ chối dịch tiêu đề do chính sách nội dung, đang chuyển sang dịch bằng Ollama (local)...")
                    else:
                        progress_callback(f"[INFO] Lỗi dịch tiêu đề bằng Gemini ({e}), đang chuyển sang dịch bằng Ollama (local)...")
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

        if progress_callback:
            progress_callback("[->] Đang gửi nội dung tới Gemini API...")

        chunks = self.split_text_into_chunks(body_text)
        total_chunks = len(chunks)
        paragraph_mappings = []

        # 1. Đảm bảo TUYỆT ĐỐI thứ tự bằng mảng độ dài cố định
        translated_chunks = [None] * total_chunks
        chunk_statuses = {}

        # Tầng 1: Dịch từng chunk tuần tự theo đúng index gốc
        for i in range(1, total_chunks + 1):
            chunk = chunks[i - 1]
            if progress_callback and total_chunks > 1:
                progress_callback(f"[->] Đang dịch phần {i}/{total_chunks}...")
            
            try:
                translated_chunk = self.translate_chunk_with_retry(
                    chunk, i, total_chunks, progress_callback, source_lang=source_lang
                )
                if not translated_chunk or not translated_chunk.strip():
                    raise ValueError("Phản hồi rỗng từ Gemini")
                chunk_statuses[i] = "direct_success"
            except Exception as e:
                is_safety = isinstance(e, GeminiSafetyBlockError)
                is_truncation = "output_truncated" in str(e)
                if is_safety:
                    info_msg = f"[INFO] Gemini từ chối dịch phần {i} do chính sách nội dung, đang chuyển sang dịch bằng Ollama (local) cho đoạn này..."
                elif is_truncation:
                    info_msg = f"[INFO] Gemini bị cắt cụt đầu ra ở phần {i}, đang chuyển sang dịch bằng Ollama (local) cho đoạn này..."
                else:
                    info_msg = f"[INFO] Lỗi dịch phần {i} ({e}), đang chuyển sang dịch bằng Ollama (local) cho đoạn này..."
                
                if progress_callback:
                    progress_callback(info_msg)
                
                try:
                    ollama_trans = self._get_ollama_fallback_translator()
                    if ollama_trans and ollama_trans.is_available():
                        translated_chunk = ollama_trans.translate(chunk, progress_callback=progress_callback, source_lang=source_lang)
                        if not translated_chunk or not translated_chunk.strip():
                            raise ValueError("Phản hồi rỗng từ Ollama fallback")
                        chunk_statuses[i] = "fallback_success"
                    else:
                        raise ValueError("Ollama không khả dụng để fallback (chưa chạy hoặc thiếu model)")
                except Exception as ollama_err:
                    if progress_callback:
                        progress_callback(f"[WARN] Fallback sang Ollama thất bại: {ollama_err}. Giữ nguyên bản gốc để vá ở Tầng 2.")
                    translated_chunk = chunk
                    if "output_truncated" in str(ollama_err) or is_truncation:
                        chunk_statuses[i] = "truncated"
                    else:
                        chunk_statuses[i] = "failed"

            translated_chunks[i - 1] = translated_chunk

        # Ghép paragraph mappings sau khi đã dịch xong tất cả các chunk theo đúng thứ tự
        for i in range(1, total_chunks + 1):
            chunk = chunks[i - 1]
            translated_chunk = translated_chunks[i - 1]
            orig_paras = [p.strip() for p in chunk.split("\n\n") if p.strip()]
            trans_paras = [p.strip() for p in translated_chunk.split("\n\n") if p.strip()]
            
            if len(orig_paras) == len(trans_paras):
                for op, tp in zip(orig_paras, trans_paras):
                    paragraph_mappings.append((op, tp, i))
            else:
                # Mismatch! Tách dịch lại riêng từng đoạn orig_p lẻ
                for op in orig_paras:
                    paragraph_mappings.append((op, "", i))

        # Tầng 2: Quét toàn file sau ghép để vá rò rỉ từng đoạn
        if progress_callback:
            progress_callback("[->] Đang quét lại toàn bộ văn bản (Tầng 2) để sửa lỗi rò rỉ ranh giới...")

        repaired_paras = []
        failed_chunks_report = []

        success_direct = 0
        success_fallback = 0

        for orig_p, trans_p, chunk_index in paragraph_mappings:
            p_failed = False
            p_reason = ""
            p_status = "direct_success"

            # 1. Nếu chunk bị cắt cụt ở Tầng 1
            if chunk_statuses.get(chunk_index) == "truncated":
                p_failed = True
                p_reason = "output_truncated"
                trans_p = f"[[MISSING_CHUNK:{chunk_index}]]"
                p_status = "failed"
            # 2. Nếu đoạn gốc chỉ chứa ký tự đặc biệt/dấu câu (không có chữ hay số), giữ nguyên bản gốc và coi như dịch thành công
            elif not re.search(r"\w", orig_p):
                trans_p = orig_p
            else:
                # Kiểm tra xem có cần xử lý dịch vá đoạn này không
                needs_repair = False
                reason = ""

                if orig_p == trans_p or not trans_p or not trans_p.strip():
                    needs_repair = True
                    reason = "untranslated"
                elif self.has_chinese_leak(trans_p):
                    needs_repair = True
                    reason = "leak"
                elif get_sentence_count(trans_p) < get_sentence_count(orig_p):
                    needs_repair = True
                    reason = "content_missing"

                if needs_repair:
                    # Định nghĩa translate_fn sử dụng API Gemini, có fallback sang Ollama
                    def translate_fn(text: str, temp: float, token_mult: float) -> str:
                        original_temp = self.temperature
                        self.temperature = temp
                        try:
                            override_tokens = int(4096 * token_mult) if token_mult > 1.0 else None
                            return self.call_gemini_api(
                                text,
                                source_lang=source_lang,
                                progress_callback=progress_callback,
                                override_max_tokens=override_tokens
                            )
                        except Exception as gemini_err:
                            is_safety = isinstance(gemini_err, GeminiSafetyBlockError)
                            if progress_callback:
                                if is_safety:
                                    progress_callback("[INFO] Gemini từ chối dịch do chính sách nội dung, đang chuyển sang dịch bằng Ollama (local)...")
                                else:
                                    progress_callback(f"[INFO] Lỗi dịch bằng Gemini ({gemini_err}), đang chuyển sang dịch bằng Ollama (local)...")
                            
                            ollama_trans = self._get_ollama_fallback_translator()
                            if ollama_trans and ollama_trans.is_available():
                                original_ollama_temp = ollama_trans.temperature
                                ollama_trans.temperature = temp
                                try:
                                    return ollama_trans.translate(text, progress_callback=progress_callback, source_lang=source_lang)
                                finally:
                                    ollama_trans.temperature = original_ollama_temp
                            else:
                                raise ValueError("Ollama fallback không khả dụng")
                        finally:
                            self.temperature = original_temp

                    re_trans, is_ok = retry_translate_paragraph(
                        orig_p=orig_p,
                        reason=reason,
                        translate_fn=translate_fn,
                        has_chinese_leak_fn=self.has_chinese_leak,
                        progress_callback=progress_callback,
                        default_temp=self.temperature,
                        temp_pass2=0.05,
                        temp_pass3=0.05
                    )

                    if not is_ok:
                        p_failed = True
                        p_reason = reason
                        trans_p = f"[[MISSING_CHUNK:{chunk_index}]]"
                        p_status = "failed"
                    else:
                        trans_p = re_trans
                        p_status = "fallback_success"
                else:
                    if chunk_statuses.get(chunk_index) == "fallback_success":
                        p_status = "fallback_success"
                    else:
                        p_status = "direct_success"

            # Tính vị trí ký tự bắt đầu đoạn lỗi trong file output
            title_offset = (len(translated_title) + 2) if translated_title else 0
            para_start_pos = len("\n\n".join(repaired_paras)) + (2 if repaired_paras else 0) + title_offset

            if p_failed:
                failed_chunks_report.append({
                    "chunk_index": chunk_index,
                    "char_position_start": para_start_pos,
                    "reason": p_reason if p_reason else "leak sau cả 2 lớp",
                    "original_text_preview": orig_p[:60]
                })

            if p_status == "direct_success":
                success_direct += 1
            elif p_status == "fallback_success":
                success_fallback += 1

            repaired_paras.append(trans_p)

        translated_body = "\n\n".join(repaired_paras)
        
        total_paras = len(paragraph_mappings)
        failed_count = len(failed_chunks_report)
        success_paras = total_paras - failed_count
        if progress_callback:
            progress_callback(f"[INFO] Hoàn thành dịch: thành công {success_paras}/{total_paras} đoạn, {failed_count} đoạn lỗi.")

        self.last_report = {
            "engine": "gemini",
            "total_chunks": total_chunks,
            "total_paras": total_paras,
            "success_direct": success_direct,
            "success_fallback": success_fallback,
            "failed_chunks": failed_chunks_report
        }

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

        # Write .translation_report.json alongside the output file
        import datetime
        report = {
            "source_file": os.path.abspath(input_path),
            "output_file": os.path.abspath(output_path),
            "engine": self.last_report.get("engine", "gemini"),
            "total_chunks": self.last_report.get("total_chunks", 0),
            "total_paras": self.last_report.get("total_paras", 0),
            "success_direct": self.last_report.get("success_direct", 0),
            "success_fallback": self.last_report.get("success_fallback", 0),
            "failed_chunks": self.last_report.get("failed_chunks", []),
            "translated_at": datetime.datetime.now().isoformat()
        }
        
        input_base = os.path.splitext(os.path.basename(input_path))[0]
        report_path = os.path.join(os.path.dirname(output_path), f"{input_base}.translation_report.json")
        with open(report_path, "w", encoding="utf-8") as rf:
            json.dump(report, rf, ensure_ascii=False, indent=2)
