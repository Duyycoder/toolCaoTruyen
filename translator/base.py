import os
import re
import json
import datetime
from typing import Callable, Optional

class TranslatorEngine:
    # Marker đánh dấu đoạn dịch lỗi trong file output
    MISSING_CHUNK_RE = re.compile(r"\[\[MISSING_CHUNK:\d+\]\]")

    def __init__(self):
        self.glossary = {}
        self.common_idioms = {}
        self.genre = "tien_hiep"
        self.last_report = {}
        self.last_report_path = None

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

    # ------------------------------------------------------------------
    # Dịch vá các đoạn lỗi ([[MISSING_CHUNK:n]]) sau khi dịch xong cả file
    # ------------------------------------------------------------------

    def _translate_single_paragraph(self, text: str, source_lang: str = "zh") -> str:
        """Dịch một đoạn văn đơn lẻ mà không làm hỏng last_report của cả file."""
        saved_report = self.last_report
        try:
            return self.translate(text, None, source_lang)
        finally:
            self.last_report = saved_report

    def refresh_failed_positions(self, output_text: str) -> None:
        """Cập nhật vị trí chính xác (ký tự + số dòng + marker) cho các đoạn lỗi
        trong last_report dựa trên nội dung file output, giúp tìm vị trí dễ hơn."""
        entries = (self.last_report or {}).get("failed_chunks", [])
        if not entries:
            return
        markers = list(self.MISSING_CHUNK_RE.finditer(output_text))
        for entry, m in zip(entries, markers):
            entry["char_position_start"] = m.start()
            entry["line_number"] = output_text.count("\n", 0, m.start()) + 1
            entry["marker"] = m.group(0)

    def rewrite_report_file(self) -> None:
        """Ghi đè file .translation_report.json với nội dung last_report hiện tại."""
        report_path = self.last_report_path
        if not report_path:
            return
        try:
            existing = {}
            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.update(self.last_report or {})
            existing["updated_at"] = datetime.datetime.now().isoformat()
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def repair_missing_chunks(
        self,
        output_path: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        source_lang: str = "zh"
    ) -> int:
        """Dịch lại các đoạn bị lỗi (marker [[MISSING_CHUNK:n]]) trong file output
        và ghép bản dịch vào đúng vị trí. Trả về số đoạn còn lỗi sau khi vá.

        Yêu cầu: last_report["failed_chunks"] chứa "original_text" (bản gốc đầy đủ
        của từng đoạn lỗi, cùng thứ tự với các marker xuất hiện trong file).
        """
        report = self.last_report or {}
        failed_entries = report.get("failed_chunks", [])
        if not failed_entries:
            return 0

        with open(output_path, "r", encoding="utf-8") as f:
            text = f.read()

        markers = list(self.MISSING_CHUNK_RE.finditer(text))
        if not markers:
            # File không còn marker nào (có thể đã được sửa tay) -> coi như sạch
            report["failed_chunks"] = []
            self.last_report = report
            self.rewrite_report_file()
            return 0

        if progress_callback:
            progress_callback(f"[->] Bắt đầu dịch vá {len(markers)} đoạn bị lỗi...")

        # Với report cũ không có "original_text", tra ngược bản gốc đầy đủ
        # từ file nguồn dựa trên preview 60 ký tự đầu
        source_paras = None
        source_file = report.get("source_file")
        if source_file and os.path.exists(source_file):
            try:
                with open(source_file, "r", encoding="utf-8") as f:
                    source_paras = [p.strip() for p in f.read().split("\n\n") if p.strip()]
            except Exception:
                source_paras = None
        used_source_idx = set()

        def find_original(entry: dict) -> str:
            orig = entry.get("original_text", "")
            if orig.strip():
                return orig
            preview = entry.get("original_text_preview", "").strip()
            if preview and source_paras:
                # Thử startswith trước (chính xác nhất)
                for si, sp in enumerate(source_paras):
                    if si not in used_source_idx and sp.startswith(preview):
                        used_source_idx.add(si)
                        return sp
                # Fallback: tìm đoạn chứa preview (preview có thể bị cắt Unicode)
                for si, sp in enumerate(source_paras):
                    if si not in used_source_idx and preview[:30] in sp:
                        used_source_idx.add(si)
                        return sp
            return ""

        pieces = []
        cursor = 0
        remaining = []
        repaired_count = 0

        # Marker thứ k trong file tương ứng với entry thứ k trong failed_chunks
        for k, m in enumerate(markers):
            entry = failed_entries[k] if k < len(failed_entries) else {}
            orig_p = find_original(entry)
            replacement = None

            if orig_p.strip():
                if progress_callback:
                    progress_callback(
                        f"[->] Dịch lại đoạn lỗi {k + 1}/{len(markers)} "
                        f"(chunk {entry.get('chunk_index', '?')}, lý do: {entry.get('reason', '?')})..."
                    )
                try:
                    candidate = self._translate_single_paragraph(orig_p, source_lang)
                    if candidate and candidate.strip() and not self.MISSING_CHUNK_RE.search(candidate):
                        leak_fn = getattr(self, "has_chinese_leak", None)
                        chinese_re = getattr(self, "chinese_char_pattern", None)
                        has_leak = leak_fn(candidate) if leak_fn else False
                        if not has_leak:
                            replacement = candidate.strip()
                        elif chinese_re:
                            # Chấp nhận nếu ít hơn 5 ký tự Hán — tốt hơn marker
                            leak_count = len(chinese_re.findall(candidate))
                            if leak_count <= 5:
                                replacement = candidate.strip()
                                if progress_callback:
                                    progress_callback(
                                        f"[WARN] Đoạn {k + 1} vẫn còn {leak_count} ký tự Hán nhưng chấp nhận (tốt hơn marker)."
                                    )
                except Exception as ex:
                    if progress_callback:
                        progress_callback(f"[WARN] Lỗi khi dịch vá đoạn {k + 1}: {ex}")
            elif progress_callback:
                progress_callback(
                    f"[WARN] Đoạn lỗi {k + 1}/{len(markers)} không có bản gốc trong report, bỏ qua."
                )

            pieces.append(text[cursor:m.start()])
            if replacement is not None:
                pieces.append(replacement)
                repaired_count += 1
                if progress_callback:
                    progress_callback(f"[OK] Đã vá xong đoạn {k + 1}/{len(markers)}.")
            else:
                pieces.append(m.group(0))
                # Bảo toàn original_text cho lần retry sau
                if orig_p.strip() and "original_text" not in entry:
                    entry["original_text"] = orig_p
                remaining.append(entry)
            cursor = m.end()

        pieces.append(text[cursor:])
        new_text = "".join(pieces)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(new_text)

        report["failed_chunks"] = remaining
        report["repaired_paras"] = report.get("repaired_paras", 0) + repaired_count
        self.last_report = report
        self.refresh_failed_positions(new_text)
        self.rewrite_report_file()

        if progress_callback:
            progress_callback(
                f"[INFO] Dịch vá hoàn tất: sửa được {repaired_count} đoạn, còn lỗi {len(remaining)} đoạn."
            )
        return len(remaining)
