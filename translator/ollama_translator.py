import os
import re
import time
import json
import urllib.request
from typing import List, Callable, Optional
from .base import TranslatorEngine
from .utils import get_sentence_count, get_sentences, get_context_before, get_context_after, retry_translate_paragraph

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
        super().__init__()
        self.model = model
        self.api_url = api_url
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.max_chunk_chars = max_chunk_chars
        self.leak_threshold_ratio = leak_threshold_percent / 100.0
        self.chinese_char_pattern = re.compile(r"[\u4e00-\u9fff]")
        self.num_predict = max(2048, max_chunk_chars * 15)
        self.last_done_reason = None

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
        Kiểm tra xem bản dịch có bị rò rỉ ký tự tiếng Trung hay không.
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
            "5. Output ONLY the translated Vietnamese text. Do not add comments, notes, or explanations.\n"
            f"6. If the input contains short questions, dialogues, or specific terms (e.g. '“对抗？”'), translate them fully into Vietnamese (e.g. '“Đối kháng?”') and do not write or copy any original {lang_name} characters in your output."
        )

        if self.glossary:
            glossary_text = "\n".join([f"- {k} -> {v}" for k, v in self.glossary.items()])
            system_instruction += (
                f"\n\nCRITICAL REQUIREMENT: You MUST strictly use the following Glossary for specific terms and names. "
                f"Do not invent or use other translations for these terms:\n{glossary_text}\n"
            )

        if is_title:
            system_instruction += "\nNote: This is the chapter title. Keep it short and preserve Markdown heading prefix."
        return system_instruction

    def extract_glossary_from_text(self, text: str, current_glossary: dict) -> dict:
        """
        Trích xuất các danh từ riêng MỚI từ văn bản bằng Ollama.
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
            "TRẢ VỀ DUY NHẤT một chuỗi JSON hợp lệ (không chứa markdown block ```json, chỉ bắt đầu bằng { và kết thúc bằng }). "
            "Định dạng JSON: {\"Chữ Hán\": \"Bản dịch Hán Việt\"}.\n"
            "Nếu không có từ mới nào đáng chú ý, hãy trả về JSON rỗng: {}\n\n"
            "Đoạn truyện:\n"
            f"{text[:1500]}"
        )
        
        try:
            res_text = self.call_ollama_api(
                text=prompt,
                system_instruction="You are a JSON data extractor. Output raw JSON only.",
                response_json=True
            )
            # Dọn dẹp JSON
            res_text = res_text.strip()
            if res_text.startswith("```json"): res_text = res_text[7:]
            if res_text.startswith("```"): res_text = res_text[3:]
            if res_text.endswith("```"): res_text = res_text[:-3]
            res_text = res_text.strip()
            
            data = json.loads(res_text)
            if isinstance(data, dict):
                return data
        except Exception as e:
            print(f"[Warning] Lỗi khi extract glossary (Ollama): {e}")
            
        return {}

    def call_ollama_api(
        self,
        text: str,
        is_title: bool = False,
        source_lang: str = "zh",
        override_num_predict: Optional[int] = None,
        system_instruction: Optional[str] = None,
        response_json: bool = False
    ) -> str:
        """
        Gọi API Ollama Chat để dịch văn bản với cơ chế thử lại nếu lỗi kết nối/timeout.
        """
        if system_instruction is None:
            system_instruction = self.build_system_prompt(source_lang, is_title)

        num_predict = override_num_predict if override_num_predict is not None else self.num_predict

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
                "num_predict": num_predict
            }
        }
        if response_json:
            payload["format"] = "json"

        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        max_retries = 2
        backoff_seconds = [3, 6]
        
        for attempt in range(max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=600) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    self.last_done_reason = res_data.get("done_reason")
                    return res_data.get("message", {}).get("content", "").strip()
            except Exception as e:
                if attempt < max_retries:
                    wait_time = backoff_seconds[attempt]
                    print(f"[WARN] Lỗi kết nối/timeout tới Ollama ({e}). Đang thử lại sau {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                raise e

    def translate_chunk_with_retry(self, chunk: str, chunk_index: int, total_chunks: int, progress_callback: Optional[Callable[[str], None]] = None, source_lang: str = "zh") -> str:
        """
        Dịch một chunk văn bản, thử lại tối đa 1 lần nếu phát hiện rò rỉ chữ Trung Quốc vượt ngưỡng.
        """
        self.last_done_reason = None
        output = self.call_ollama_api(chunk, source_lang=source_lang)
        
        # 1. Kiểm tra giới hạn token (done_reason == "length")
        if self.last_done_reason == "length":
            warn_msg = f"[WARN] Chunk {chunk_index} bị cắt cụt do giới hạn token. Đang thử lại với num_predict lớn hơn..."
            if progress_callback:
                progress_callback(warn_msg)
            
            # Thử lại với 1.5x tokens
            retry_num_predict = int(self.num_predict * 1.5)
            output = self.call_ollama_api(chunk, source_lang=source_lang, override_num_predict=retry_num_predict)
            
            if self.last_done_reason == "length":
                raise ValueError("output_truncated")
        
        # 2. Kiểm tra rò rỉ chữ Trung Quốc
        if self.has_chinese_leak(output):
            warn_msg = f"[WARN] Phát hiện rò rỉ chữ Trung ở chunk {chunk_index} ({len(self.chinese_char_pattern.findall(output))} ký tự). Tiến hành dịch lại ở nhiệt độ thấp hơn..."
            if progress_callback:
                progress_callback(warn_msg)
            
            # Thử lại lượt 2 với temperature thấp hơn để tăng tính tuân thủ
            original_temp = self.temperature
            self.temperature = 0.02
            try:
                output = self.call_ollama_api(chunk, source_lang=source_lang)
                if self.last_done_reason == "length":
                    raise ValueError("output_truncated")
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
                    raise ValueError("Phản hồi rỗng từ Ollama")
                chunk_statuses[i] = "direct_success"
            except Exception as e:
                if "output_truncated" in str(e):
                    if progress_callback:
                        progress_callback(f"[WARN] Lỗi dịch chunk {i}: Output bị cắt cụt do giới hạn token. Giữ nguyên bản gốc để vá ở Tầng 2.")
                    chunk_statuses[i] = "truncated"
                else:
                    if progress_callback:
                        progress_callback(f"[WARN] Lỗi dịch chunk {i}: {e}. Giữ nguyên bản gốc để vá ở Tầng 2.")
                    chunk_statuses[i] = "failed"
                translated_chunk = chunk

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

            if chunk_statuses.get(chunk_index) == "truncated":
                p_failed = True
                p_reason = "output_truncated"
                trans_p = f"[[MISSING_CHUNK:{chunk_index}]]"
                p_status = "failed"
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
                    # Định nghĩa translate_fn sử dụng API Ollama
                    def translate_fn(text: str, temp: float, token_mult: float) -> str:
                        original_temp = self.temperature
                        self.temperature = temp
                        try:
                            override_predict = int(self.num_predict * token_mult) if token_mult > 1.0 else None
                            return self.call_ollama_api(text, source_lang=source_lang, override_num_predict=override_predict)
                        finally:
                            self.temperature = original_temp

                    re_trans, is_ok = retry_translate_paragraph(
                        orig_p=orig_p,
                        reason=reason,
                        translate_fn=translate_fn,
                        has_chinese_leak_fn=self.has_chinese_leak,
                        progress_callback=progress_callback,
                        default_temp=self.temperature,
                        temp_pass2=0.02,
                        temp_pass3=0.02
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
            "engine": "ollama",
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

        # Write .translation_report.json alongside the output file
        import datetime
        report = {
            "source_file": os.path.abspath(input_path),
            "output_file": os.path.abspath(output_path),
            "engine": self.last_report.get("engine", "ollama"),
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

