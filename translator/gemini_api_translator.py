import os
import re
import time
import json
import urllib.request
import urllib.error
from typing import List, Callable, Optional
from .gemini_translator import GeminiTranslator, GeminiSafetyBlockError
from .base import TranslatorEngine
from .utils import get_sentence_count, get_sentences, get_context_before, get_context_after, retry_translate_paragraph


class GeminiApiTranslator(GeminiTranslator):
    """
    Engine dịch thuật sử dụng Gemini API thông qua endpoint tương thích OpenAI.
    Cho phép kết nối đến server local/offline chạy trên base_url tùy chỉnh.
    Kế thừa toàn bộ logic chunking, kiểm tra rò rỉ, và dịch 2 tầng từ GeminiTranslator.
    Chỉ override phần gọi API để chuyển sang định dạng OpenAI Chat Completions.
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "http://localhost:7860/v1",
        model: str = "gemini-2.5-flash",
        temperature: float = 0.2,
        max_chunk_chars: int = 1000,
        leak_threshold_percent: float = 10.0
    ):
        super().__init__(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_chunk_chars=max_chunk_chars,
            leak_threshold_percent=leak_threshold_percent
        )
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        """
        Kiểm tra xem API Key và Base URL đã được cấu hình hay chưa.
        """
        return bool(self.api_key and self.api_key.strip() and self.base_url and self.base_url.strip())

    def _execute_api_call(self, url: str, payload: dict) -> str:
        """
        Ghi đè _execute_api_call để gửi request theo định dạng OpenAI Chat Completions.
        Tham số url ở đây sẽ được bỏ qua, thay vào đó sử dụng self.base_url.
        """
        api_url = f"{self.base_url}/chat/completions"

        # Chuyển đổi payload từ định dạng Gemini sang OpenAI Chat Completions
        messages = []

        # System instruction -> system message
        system_instruction = payload.get("systemInstruction", {})
        if system_instruction:
            parts = system_instruction.get("parts", [])
            if parts:
                system_text = parts[0].get("text", "")
                if system_text:
                    messages.append({"role": "system", "content": system_text})

        # Contents -> user message
        contents = payload.get("contents", [])
        if contents:
            parts = contents[0].get("parts", [])
            if parts:
                user_text = parts[0].get("text", "")
                if user_text:
                    messages.append({"role": "user", "content": user_text})

        # Xây dựng payload OpenAI
        openai_payload = {
            "model": self.model,
            "messages": messages,
            "temperature": payload.get("generationConfig", {}).get("temperature", self.temperature),
        }

        # maxOutputTokens -> max_tokens
        max_tokens = payload.get("generationConfig", {}).get("maxOutputTokens")
        if max_tokens:
            openai_payload["max_tokens"] = max_tokens

        # responseMimeType -> response_format
        response_mime = payload.get("generationConfig", {}).get("responseMimeType")
        if response_mime == "application/json":
            openai_payload["response_format"] = {"type": "json_object"}

        req = urllib.request.Request(
            api_url,
            data=json.dumps(openai_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
        )

        with urllib.request.urlopen(req, timeout=90) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            choices = res_data.get("choices", [])
            if choices:
                choice = choices[0]
                # Kiểm tra finish_reason
                finish_reason = choice.get("finish_reason", "")
                # Chuyển đổi finish_reason từ OpenAI sang Gemini format để tương thích
                if finish_reason == "length":
                    self.last_finish_reason = "MAX_TOKENS"
                elif finish_reason == "content_filter":
                    raise GeminiSafetyBlockError("Nội dung bị từ chối do chính sách an toàn")
                else:
                    self.last_finish_reason = finish_reason

                message = choice.get("message", {})
                content = message.get("content", "").strip()
                if content:
                    return content

            raise ValueError(f"API trả về kết quả trống: {res_data}")

    def call_gemini_api(self, text: str, is_title: bool = False, source_lang: str = "zh",
                        progress_callback: Optional[Callable[[str], None]] = None,
                        override_max_tokens: Optional[int] = None) -> str:
        """
        Gọi API qua endpoint OpenAI-compatible với cơ chế tự động thử lại nếu gặp lỗi 429/503.
        """
        if not self.is_available():
            raise ValueError("Gemini API (Offline) chưa được cấu hình. Vui lòng nhập API Key và Base URL.")

        system_instruction = self.build_system_prompt(source_lang, is_title)
        max_tokens = override_max_tokens if override_max_tokens is not None else 4096

        # Xây dựng payload theo định dạng Gemini (sẽ được _execute_api_call chuyển đổi)
        payload = {
            "contents": [
                {"parts": [{"text": text}]}
            ],
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": max_tokens
            },
            "safetySettings": []
        }

        max_retries = 3
        backoff_seconds = [6, 12, 24]

        for attempt in range(max_retries + 1):
            # Enforce request spacing delay (ít nhất 1.0s giữa các request liên tiếp cho local)
            elapsed = time.time() - self.last_request_time
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)
            self.last_request_time = time.time()

            try:
                return self._execute_api_call(None, payload)
            except urllib.error.HTTPError as e:
                # 1. Lỗi 400 (Bad Request)
                if e.code == 400:
                    try:
                        err_body = e.read().decode("utf-8")
                        err_json = json.loads(err_body)
                        err_msg = err_json.get("error", {}).get("message", "Unknown Bad Request")
                    except Exception:
                        err_msg = "Unknown Bad Request"
                    raise ValueError(f"Lỗi định dạng yêu cầu gửi tới Gemini API (Offline): {err_msg}")

                # 2. Lỗi 429 (Rate Limit) hoặc 503 (Unavailable)
                if e.code in (429, 503) and attempt < max_retries:
                    wait_time = backoff_seconds[attempt]
                    retry_after = e.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait_time = int(retry_after)

                    log_msg = f"[WARN] Lỗi {e.code} từ server local, đang chờ {wait_time}s để thử lại..."
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
                raise ValueError(f"Lỗi HTTP {e.code} từ Gemini API (Offline): {err_body}")
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

    def extract_glossary_from_text(self, text: str, current_glossary: dict) -> dict:
        """
        Trích xuất các danh từ riêng MỚI từ văn bản qua endpoint OpenAI-compatible.
        """
        prompt = (
            "Dưới đây là một đoạn truyện tiên hiệp tiếng Trung.\n"
            "Hãy phân tích và tìm ra tất cả các Tên nhân vật, Địa danh, Tên môn phái, Tuyệt chiêu, hoặc thuật ngữ riêng ĐÁNG CHÚ Ý xuất hiện trong đoạn.\n"
            "Dịch chúng sang âm Hán Việt chuẩn xác (Ví dụ: 顾安 -> Cố An, 孟浪 -> Mạnh Lãng, 太玄门 -> Thái Huyền Môn).\n"
        )
        if current_glossary:
            existing_keys = ", ".join(current_glossary.keys())
            prompt += f"BỎ QUA và KHÔNG trích xuất lại các từ đã có trong danh sách sau: {existing_keys}.\n"

        prompt += (
            "TRẢ VỀ DUY NHẤT một chuỗi JSON hợp lệ (không chứa markdown markdown block ```json, chỉ có ngoặc nhọn). "
            "Định dạng JSON: {\"Chữ Hán\": \"Bản dịch Hán Việt\"}.\n"
            "Nếu không có từ mới nào đáng chú ý, hãy trả về: {}\n"
            "Đoạn truyện:\n"
            f"{text[:3000]}"
        )

        # Xây dựng payload Gemini format (sẽ được _execute_api_call chuyển đổi)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": "You are a data extractor. Output ONLY raw JSON."}]},
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
        }

        try:
            res_text = self._execute_api_call(None, payload)
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
            print(f"[Warning] Lỗi khi extract glossary (Gemini API Offline): {e}")

        return {}

    def translate(self, text: str, progress_callback: Optional[Callable[[str], None]] = None, source_lang: str = "zh") -> str:
        """
        Gọi hàm translate từ GeminiTranslator gốc, chỉ thay đổi tên engine trong report.
        """
        if not self.is_available():
            err_msg = "Gemini API (Offline) chưa được cấu hình. Vui lòng nhập API Key và Base URL trong phần Cấu hình."
            if progress_callback:
                progress_callback(f"[ERROR] {err_msg}")
            raise ValueError(err_msg)

        # Gọi logic translate gốc từ GeminiTranslator (kế thừa toàn bộ chunking 2 tầng)
        result = super().translate(text, progress_callback, source_lang)

        # Cập nhật engine name trong report
        if hasattr(self, 'last_report') and self.last_report:
            self.last_report["engine"] = "gemini_api"

        return result
