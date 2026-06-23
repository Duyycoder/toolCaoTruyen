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
        if is_title:
            system_instruction += "\nNote: This is the chapter title. Keep it short and preserve Markdown heading prefix."
        return system_instruction

    def call_ollama_api(self, text: str, is_title: bool = False, source_lang: str = "zh", override_num_predict: Optional[int] = None) -> str:
        """
        Gọi API Ollama Chat để dịch văn bản.
        """
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

        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=90) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            self.last_done_reason = res_data.get("done_reason")
            return res_data.get("message", {}).get("content", "").strip()

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
                paragraph_mappings.append(("\n\n".join(orig_paras), "\n\n".join(trans_paras), i))

        # Tầng 2: Quét toàn file sau ghép để vá rò rỉ từng đoạn
        if progress_callback:
            progress_callback("[->] Đang quét lại toàn bộ văn bản (Tầng 2) để sửa lỗi rò rỉ ranh giới...")

        repaired_paras = []
        failed_chunks_report = []

        for orig_p, trans_p, chunk_index in paragraph_mappings:
            p_failed = False
            p_reason = ""

            if chunk_statuses.get(chunk_index) == "truncated":
                p_failed = True
                p_reason = "output_truncated"
                trans_p = orig_p
            elif not re.search(r"\w", orig_p):
                trans_p = orig_p
            elif orig_p == trans_p or not trans_p or not trans_p.strip():
                # Nếu đoạn dịch giống hệt đoạn gốc hoặc bị rỗng (chưa được dịch tí nào do lỗi cả chunk ở Tầng 1),
                # không chạy dịch vá từng đoạn nữa để tiết kiệm thời gian chạy mô hình
                p_failed = True
                p_reason = "untranslated"
                trans_p = orig_p
            elif self.has_chinese_leak(trans_p):
                if progress_callback:
                    progress_callback(f"[->] Phát hiện rò rỉ chữ Hán ở đoạn: '{trans_p[:30]}...'. Tiến hành dịch vá...")
                
                try:
                    re_trans = self.call_ollama_api(orig_p, source_lang=source_lang)
                    if self.has_chinese_leak(re_trans):
                        # Thử lại lần cuối ở nhiệt độ 0.02
                        original_temp = self.temperature
                        self.temperature = 0.02
                        try:
                            re_trans = self.call_ollama_api(orig_p, source_lang=source_lang)
                        finally:
                            self.temperature = original_temp
                except Exception:
                    re_trans = orig_p
                
                if not re_trans or re_trans == orig_p or self.has_chinese_leak(re_trans):
                    p_failed = True
                    p_reason = "leak sau cả 2 lớp"
                    trans_p = orig_p
                    if progress_callback:
                        progress_callback(f"[WARN] Vá thất bại, giữ nguyên bản gốc đoạn: '{orig_p[:30]}...'")
                else:
                    trans_p = re_trans
                    if progress_callback:
                        progress_callback(f"[SUCCESS] Vá thành công: '{re_trans[:30]}...'")
            else:
                trans_p = trans_p

            # Tính vị trí ký tự bắt đầu đoạn lỗi trong file output
            title_offset = (len(translated_title) + 2) if translated_title else 0
            para_start_pos = len("\n\n".join(repaired_paras)) + (2 if repaired_paras else 0) + title_offset

            if p_failed:
                chunk_statuses[chunk_index] = "failed"
                failed_chunks_report.append({
                    "chunk_index": chunk_index,
                    "char_position_start": para_start_pos,
                    "reason": p_reason if p_reason else "leak sau cả 2 lớp",
                    "original_text_preview": orig_p[:60]
                })

            repaired_paras.append(trans_p)

        translated_body = "\n\n".join(repaired_paras)
        
        total_paras = len(paragraph_mappings)
        failed_count = len(failed_chunks_report)
        success_paras = total_paras - failed_count
        if progress_callback:
            progress_callback(f"[INFO] Hoàn thành dịch: thành công {success_paras}/{total_paras} đoạn, {failed_count} đoạn lỗi.")

        # Compile report statistics
        success_direct = sum(1 for status in chunk_statuses.values() if status == "direct_success")

        self.last_report = {
            "engine": "ollama",
            "total_chunks": total_chunks,
            "total_paras": total_paras,
            "success_direct": success_direct,
            "success_fallback": 0,
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

