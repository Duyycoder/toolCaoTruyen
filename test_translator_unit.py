import os
import unittest
from unittest.mock import MagicMock
from translator.ollama_translator import OllamaTranslator
from translator.gemini_translator import GeminiTranslator
from core.config_manager import get_default_config, load_config, save_full_config

class TestOllamaTranslator(unittest.TestCase):
    def setUp(self):
        # Tạo translator mock với kích thước chunk nhỏ (100 ký tự) để dễ kiểm thử
        self.translator = OllamaTranslator(
            model="qwen2.5:7b-instruct",
            num_ctx=4096,
            max_chunk_chars=100
        )

    def test_split_text_into_chunks(self):
        self.translator.max_chunk_chars = 30
        text = (
            "Đoạn văn thứ nhất.\n\n"
            "Đoạn văn thứ hai."
        )
        chunks = self.translator.split_text_into_chunks(text)
        
        # Kiểm tra văn bản được chia thành nhiều chunk
        self.assertTrue(len(chunks) > 1)
        
        # Kiểm tra nội dung được nối lại trùng khớp gốc
        reconstructed = "\n\n".join(chunks)
        self.assertEqual(reconstructed.strip(), text.strip())

    def test_contains_chinese_leak(self):
        # Không có chữ Hán
        self.assertFalse(self.translator.contains_chinese_leak("Bản dịch hoàn toàn tiếng Việt."))
        
        # Rò rỉ chữ Hán (nhiều hơn 5 ký tự và chiếm tỷ lệ vượt quá leak_threshold_ratio)
        self.assertTrue(self.translator.contains_chinese_leak("Bản dịch chứa chữ 奇迹种子魔法少女 cực mạnh."))
        
        # Có chữ Hán (Cơ chế Zero Tolerance: dù chỉ 1 ký tự vẫn cấu thành rò rỉ)
        self.assertTrue(self.translator.contains_chinese_leak("Chương 9: 魔法"))

    def test_build_system_prompt(self):
        prompt_zh = self.translator.build_system_prompt(source_lang="zh")
        prompt_ja = self.translator.build_system_prompt(source_lang="ja")
        prompt_ko = self.translator.build_system_prompt(source_lang="ko")
        prompt_en = self.translator.build_system_prompt(source_lang="en")

        self.assertIn("Chinese", prompt_zh)
        self.assertIn("Japanese", prompt_ja)
        self.assertIn("Korean", prompt_ko)
        self.assertIn("English", prompt_en)

    def test_translate_tier1_retry_success(self):
        # Giả lập: Lượt 1 dịch chunk bị leak chữ Trung, Lượt 2 dịch thành công sạch sẽ
        call_count = 0
        def mock_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            nonlocal call_count
            call_count += 1
            if is_title:
                return "Dịch Tiêu Đề"
            if call_count == 2:  # Lượt 1 của chunk 1
                return "Bản dịch chứa 奇迹种子魔法少女"
            return "Bản dịch tiếng Việt hoàn hảo."

        self.translator.call_ollama_api = MagicMock(side_effect=mock_call)
        self.translator.is_available = MagicMock(return_value=True)

        text = (
            "# Tiêu đề\n"
            "Nội dung cần dịch."
        )
        result = self.translator.translate(text)
        
        # Tổng số lần gọi API: 1 tiêu đề + 2 chunk (do retry) = 3 lần
        self.assertEqual(self.translator.call_ollama_api.call_count, 3)
        self.assertIn("Bản dịch tiếng Việt hoàn hảo.", result)

    def test_translate_tier2_repair_success(self):
        # Giả lập: Chunk dịch bị rò rỉ kể cả sau retry, 
        # nhưng khi quét Tier 2 vá từng đoạn thì thành công không leak.
        call_count = 0
        def mock_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            nonlocal call_count
            call_count += 1
            if is_title:
                return "Dịch Tiêu Đề"
            if call_count <= 3:  # Lượt 1 và Lượt 2 retry của chunk 1
                return "Bản dịch bị rò rỉ chữ Trung 奇迹种子魔法少女"
            # Lần gọi vá đoạn ở Tier 2 (gọi lần thứ 4)
            return "Đoạn văn đã được vá sạch sẽ."

        self.translator.call_ollama_api = MagicMock(side_effect=mock_call)
        self.translator.is_available = MagicMock(return_value=True)

        text = (
            "# Tiêu đề\n"
            "Một đoạn văn."
        )
        result = self.translator.translate(text)
        
        # Kiểm tra xem đoạn dịch có được thay bằng bản dịch vá ở Tier 2
        self.assertIn("Đoạn văn đã được vá sạch sẽ.", result)
        self.assertNotIn("> ⚠️", result)

    def test_translate_tier2_repair_fallback(self):
        # Giả lập: Kể cả sau khi vá đoạn ở Tier 2 vẫn bị rò rỉ chữ Trung
        def mock_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            if is_title:
                return "Dịch Tiêu Đề"
            return "Rò rỉ chữ Hán hoài 奇迹种子魔法少女"


        self.translator.call_ollama_api = MagicMock(side_effect=mock_call)
        self.translator.is_available = MagicMock(return_value=True)

        text = (
            "# Tiêu đề\n"
            "Văn bản bị lỗi."
        )
        result = self.translator.translate(text)
        
        # Kiểm tra xem văn bản được trả về sạch (không chứa cảnh báo chèn trong md) và lưu lỗi vào report
        self.assertNotIn("> ⚠️", result)
        self.assertIn("[[MISSING_CHUNK:1]]", result)
        
        report = self.translator.last_report
        self.assertEqual(report["total_chunks"], 1)
        self.assertEqual(len(report["failed_chunks"]), 1)
        self.assertEqual(report["failed_chunks"][0]["chunk_index"], 1)
        self.assertEqual(report["failed_chunks"][0]["reason"], "leak")

    def test_translate_empty_chunk_fallback(self):
        self.translator.call_ollama_api = MagicMock(return_value="")
        self.translator.is_available = MagicMock(return_value=True)
        text = "Văn bản gốc tiếng Trung."
        result = self.translator.translate(text)
        self.assertIn("[[MISSING_CHUNK:1]]", result)
        self.assertEqual(len(self.translator.last_report["failed_chunks"]), 1)

    def test_has_chinese_leak(self):
        self.assertFalse(self.translator.has_chinese_leak("Bản dịch tiếng Việt."))
        self.assertTrue(self.translator.has_chinese_leak("Bản dịch chứa 奇迹种子魔法少女"))
        large_text = "Đoạn 1 tiếng Việt.\n\nĐoạn 2 chứa 奇迹种子魔法少女.\n\nĐoạn 3 tiếng Việt dài thật là dài để làm loãng tỷ lệ rò rỉ."
        self.assertTrue(self.translator.has_chinese_leak(large_text))

    def test_translate_truncation_retry_success(self):
        # Lượt 1 bị truncated (done_reason == "length"), lượt 2 retry thành công
        call_count = 0
        def mock_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            nonlocal call_count
            call_count += 1
            if is_title:
                return "Dịch Tiêu Đề"
            if call_count == 2:  # Lần đầu của chunk 1
                self.translator.last_done_reason = "length"
                return "Cắt cụt..."
            self.translator.last_done_reason = "stop"
            return "Bản dịch đầy đủ hoàn hảo."

        self.translator.call_ollama_api = MagicMock(side_effect=mock_call)
        self.translator.is_available = MagicMock(return_value=True)

        text = (
            "# Tiêu đề\n"
            "Nội dung cần dịch."
        )
        result = self.translator.translate(text)
        
        # Lần gọi: 1 tiêu đề + 1 chunk (thử lần 1, ra length) + 1 chunk (retry với 1.5x) = 3 lần
        self.assertEqual(self.translator.call_ollama_api.call_count, 3)
        self.assertIn("Bản dịch đầy đủ hoàn hảo.", result)

    def test_translate_truncation_retry_fail(self):
        # Lượt 1 bị truncated, lượt 2 retry vẫn bị truncated -> thất bại với output_truncated
        def mock_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            if is_title:
                return "Dịch Tiêu Đề"
            self.translator.last_done_reason = "length"
            return "Cắt cụt..."

        self.translator.call_ollama_api = MagicMock(side_effect=mock_call)
        self.translator.is_available = MagicMock(return_value=True)

        text = (
            "# Tiêu đề\n"
            "Nội dung bị lỗi."
        )
        result = self.translator.translate(text)
        
        # Phải trả về bản gốc và ghi nhận lỗi output_truncated
        self.assertIn("[[MISSING_CHUNK:1]]", result)
        report = self.translator.last_report
        self.assertEqual(report["total_chunks"], 1)
        self.assertEqual(len(report["failed_chunks"]), 1)
        self.assertEqual(report["failed_chunks"][0]["reason"], "output_truncated")

    def test_translate_untranslated_tier2_fallback_success(self):
        # Giả lập: Tầng 1 dịch lỗi (nhận bản gốc làm translated_chunk), 
        # nhưng Tầng 2 dịch lại từng đoạn nhỏ thành công.
        call_count = 0
        def mock_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            nonlocal call_count
            call_count += 1
            if is_title:
                return "Dịch Tiêu Đề"
            if call_count == 2:  # Lượt Tầng 1 của chunk 1 (ném lỗi)
                raise ValueError("Timeout error")
            # Lượt Tầng 2 vá đoạn
            return "Đoạn văn được dịch thành công ở Tầng 2"

        self.translator.call_ollama_api = MagicMock(side_effect=mock_call)
        self.translator.is_available = MagicMock(return_value=True)

        text = (
            "# Tiêu đề\n"
            "Văn bản chưa dịch."
        )
        result = self.translator.translate(text)
        
        # Kết quả phải chứa bản dịch thành công ở Tầng 2
        self.assertIn("Đoạn văn được dịch thành công ở Tầng 2", result)
        self.assertEqual(len(self.translator.last_report["failed_chunks"]), 0)

    def test_call_ollama_api_timeout_retry(self):
        # Giả lập urllib.request.urlopen ném lỗi lần 1, thành công lần 2
        import urllib.request
        from unittest.mock import patch
        
        call_count = 0
        
        def mock_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("connection timed out")
            import io
            response = MagicMock()
            response.__enter__.return_value = io.BytesIO('{"message": {"content": "Bản dịch thử"}, "done_reason": "stop"}'.encode("utf-8"))
            return response
            
        # We patch urllib.request.urlopen
        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            # We patch time.sleep to avoid waiting in tests
            with patch('time.sleep', return_value=None):
                result = self.translator.call_ollama_api("Văn bản gốc")
                self.assertEqual(result, "Bản dịch thử")
                self.assertEqual(call_count, 2) # Verified retry was executed

    def test_config_schema(self):
        config = get_default_config()
        self.assertIn("translator", config)
        self.assertIn("engine", config["translator"])
        self.assertIn("ollama_model", config["translator"])
        self.assertIn("leak_threshold_percent", config["translator"])
        self.assertIn("gemini_api_key", config["translator"])
        self.assertIn("gemini_model", config["translator"])

        # Ghi thử config và đọc lại
        save_full_config(config)
        loaded = load_config()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["translator"]["engine"], "ollama")

class TestGeminiTranslator(unittest.TestCase):
    def setUp(self):
        self.translator = GeminiTranslator(
            api_key="mock-key",
            model="gemini-2.5-flash",
            max_chunk_chars=100
        )

    def test_split_text_into_chunks(self):
        self.translator.max_chunk_chars = 30
        text = (
            "Đoạn văn thứ nhất.\n\n"
            "Đoạn văn thứ hai."
        )
        chunks = self.translator.split_text_into_chunks(text)
        self.assertTrue(len(chunks) > 1)
        reconstructed = "\n\n".join(chunks)
        self.assertEqual(reconstructed.strip(), text.strip())

    def test_contains_chinese_leak(self):
        self.assertFalse(self.translator.contains_chinese_leak("Bản dịch hoàn toàn tiếng Việt."))
        # Rò rỉ chữ Hán (Cơ chế Zero Tolerance: dù chỉ 1 ký tự vẫn cấu thành rò rỉ)
        self.assertTrue(self.translator.contains_chinese_leak("Bản dịch chứa chữ 奇迹种子魔法少女 cực mạnh."))
        self.assertTrue(self.translator.contains_chinese_leak("Chương 9: 魔法"))

    def test_build_system_prompt(self):
        prompt_zh = self.translator.build_system_prompt(source_lang="zh")
        self.assertIn("Chinese", prompt_zh)

    def test_translate_tier1_retry_success(self):
        call_count = 0
        def mock_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            nonlocal call_count
            call_count += 1
            if is_title:
                return "Dịch Tiêu Đề"
            if call_count == 2:  # Lượt 1 của chunk 1
                return "Bản dịch chứa 奇迹种子魔法少女"
            return "Bản dịch tiếng Việt hoàn hảo."

        self.translator.call_gemini_api = MagicMock(side_effect=mock_call)
        self.translator.is_available = MagicMock(return_value=True)

        text = (
            "# Tiêu đề\n"
            "Nội dung cần dịch."
        )
        result = self.translator.translate(text)
        self.assertEqual(self.translator.call_gemini_api.call_count, 3)
        self.assertIn("Bản dịch tiếng Việt hoàn hảo.", result)

    def test_translate_tier2_repair_success(self):
        call_count = 0
        def mock_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            nonlocal call_count
            call_count += 1
            if is_title:
                return "Dịch Tiêu Đề"
            if call_count <= 3:  # Lượt 1 và Lượt 2 retry của chunk 1
                return "Bản dịch bị rò rỉ chữ Trung 奇迹种子魔法少女"
            return "Đoạn văn đã được vá sạch sẽ."

        self.translator.call_gemini_api = MagicMock(side_effect=mock_call)
        self.translator.is_available = MagicMock(return_value=True)

        text = (
            "# Tiêu đề\n"
            "Một đoạn văn."
        )
        result = self.translator.translate(text)
        self.assertIn("Đoạn văn đã được vá sạch sẽ.", result)
        self.assertNotIn("> ⚠️", result)

    def test_translate_fallback_to_ollama_success(self):
        from translator.gemini_translator import GeminiSafetyBlockError
        
        # Giả lập: Gemini bị chặn nội dung (ném GeminiSafetyBlockError)
        def mock_gemini_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            if is_title:
                return "Dịch Tiêu Đề"
            raise GeminiSafetyBlockError("Nội dung nhạy cảm")
            
        self.translator.call_gemini_api = MagicMock(side_effect=mock_gemini_call)
        self.translator.is_available = MagicMock(return_value=True)
        
        # Giả lập Ollama khả dụng và dịch thành công
        mock_ollama = MagicMock()
        mock_ollama.is_available.return_value = True
        mock_ollama.translate.return_value = "Bản dịch từ Ollama thành công."
        
        self.translator._get_ollama_fallback_translator = MagicMock(return_value=mock_ollama)
        
        text = (
            "# Tiêu đề\n"
            "Nội dung bị chặn bởi Gemini."
        )
        result = self.translator.translate(text)
        
        self.assertIn("Bản dịch từ Ollama thành công.", result)
        self.assertNotIn("> ⚠️", result)
        mock_ollama.translate.assert_called_once()

    def test_translate_fallback_to_ollama_fail(self):
        from translator.gemini_translator import GeminiSafetyBlockError
        
        # Giả lập: Gemini bị chặn nội dung
        def mock_gemini_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            if is_title:
                return "Dịch Tiêu Đề"
            raise GeminiSafetyBlockError("Nội dung nhạy cảm")
            
        self.translator.call_gemini_api = MagicMock(side_effect=mock_gemini_call)
        self.translator.is_available = MagicMock(return_value=True)
        
        # Giả lập Ollama không khả dụng (hoặc lỗi khi dịch)
        mock_ollama = MagicMock()
        mock_ollama.is_available.return_value = False
        
        self.translator._get_ollama_fallback_translator = MagicMock(return_value=mock_ollama)
        
        text = (
            "# Tiêu đề\n"
            "Nội dung bị chặn bởi Gemini."
        )
        result = self.translator.translate(text)
        
        # Vì Ollama không khả dụng, đoạn đó sẽ bị giữ nguyên bản gốc mà không chèn cảnh báo md, và ghi vào report
        self.assertNotIn("> ⚠️", result)
        self.assertIn("[[MISSING_CHUNK:1]]", result)
        
        report = self.translator.last_report
        self.assertEqual(report["total_chunks"], 1)
        self.assertEqual(len(report["failed_chunks"]), 1)
        self.assertEqual(report["failed_chunks"][0]["chunk_index"], 1)
        self.assertEqual(report["failed_chunks"][0]["reason"], "untranslated")

    def test_translate_order_preservation_with_latency(self):
        from translator.gemini_translator import GeminiSafetyBlockError
        import time

        self.translator.max_chunk_chars = 10

        # Giả lập:
        # - Chunk 0 ("Chunk Zero."): Gemini dịch thành công ngay lập tức.
        # - Chunk 1 ("Chunk One."): Gemini bị block nội dung, chuyển sang fallback Ollama. 
        #   Fallback Ollama tốn nhiều thời gian (giả lập sleep 0.1s).
        # - Chunk 2 ("Chunk Two."): Gemini dịch thành công ngay lập tức.
        
        def mock_gemini_call(text, *args, **kwargs):
            if "Zero" in text:
                return "Dịch Zero"
            elif "One" in text:
                raise GeminiSafetyBlockError("Nội dung nhạy cảm ở chunk 1")
            elif "Two" in text:
                return "Dịch Two"
            return text

        self.translator.call_gemini_api = MagicMock(side_effect=mock_gemini_call)
        self.translator.is_available = MagicMock(return_value=True)

        # Mock Ollama fallback translator
        mock_ollama = MagicMock()
        mock_ollama.is_available.return_value = True
        
        def mock_ollama_translate(text, *args, **kwargs):
            time.sleep(0.1)  # Giả lập độ trễ / tốn thời gian hơn
            if "One" in text:
                return "Dịch One Fallback"
            return text
            
        mock_ollama.translate = MagicMock(side_effect=mock_ollama_translate)
        self.translator._get_ollama_fallback_translator = MagicMock(return_value=mock_ollama)

        text = (
            "Chunk Zero.\n\n"
            "Chunk One.\n\n"
            "Chunk Two."
        )

        result = self.translator.translate(text)

        # Kiểm tra thứ tự văn bản ghép cuối cùng phải đúng là 0 -> 1 -> 2
        # Tức là: Dịch Zero -> Dịch One Fallback -> Dịch Two
        expected_result = "Dịch Zero\n\nDịch One Fallback\n\nDịch Two"
        self.assertEqual(result.strip(), expected_result.strip())
        
        # Xác nhận trong last_report
        report = self.translator.last_report
        self.assertEqual(report["total_chunks"], 3)
        self.assertEqual(report["success_direct"], 2)
        self.assertEqual(report["success_fallback"], 1)
        self.assertEqual(len(report["failed_chunks"]), 0)

    def test_translate_empty_chunk_fallback(self):
        self.translator.call_gemini_api = MagicMock(return_value="")
        self.translator.is_available = MagicMock(return_value=True)
        mock_ollama = MagicMock()
        mock_ollama.is_available.return_value = True
        mock_ollama.translate = MagicMock(return_value="Dịch thành công từ Ollama")
        self.translator._get_ollama_fallback_translator = MagicMock(return_value=mock_ollama)
        text = "Văn bản gốc."
        result = self.translator.translate(text)
        self.assertIn("Dịch thành công từ Ollama", result)

    def test_translate_truncation_retry_success(self):
        # Lượt 1 bị truncated (finishReason == "MAX_TOKENS"), lượt 2 retry thành công
        call_count = 0
        def mock_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            nonlocal call_count
            call_count += 1
            if is_title:
                return "Dịch Tiêu Đề"
            if call_count == 2:
                self.translator.last_finish_reason = "MAX_TOKENS"
                return "Cắt cụt..."
            self.translator.last_finish_reason = "STOP"
            return "Bản dịch đầy đủ hoàn hảo."

        self.translator.call_gemini_api = MagicMock(side_effect=mock_call)
        self.translator.is_available = MagicMock(return_value=True)

        text = (
            "# Tiêu đề\n"
            "Nội dung cần dịch."
        )
        result = self.translator.translate(text)
        
        self.assertEqual(self.translator.call_gemini_api.call_count, 3)
        self.assertIn("Bản dịch đầy đủ hoàn hảo.", result)

    def test_translate_truncation_retry_fail(self):
        # Lượt 1 bị truncated, lượt 2 retry vẫn bị truncated -> thất bại với output_truncated
        def mock_call(text, *args, **kwargs):
            is_title = kwargs.get("is_title", False)
            if is_title:
                return "Dịch Tiêu Đề"
            self.translator.last_finish_reason = "MAX_TOKENS"
            return "Cắt cụt..."

        self.translator.call_gemini_api = MagicMock(side_effect=mock_call)
        self.translator.is_available = MagicMock(return_value=True)
        # Disable fallback to keep tests pure
        self.translator._get_ollama_fallback_translator = MagicMock(return_value=None)

        text = (
            "# Tiêu đề\n"
            "Nội dung bị lỗi."
        )
        result = self.translator.translate(text)
        
        self.assertIn("[[MISSING_CHUNK:1]]", result)
        report = self.translator.last_report
        self.assertEqual(report["total_chunks"], 1)
        self.assertEqual(len(report["failed_chunks"]), 1)
        self.assertEqual(report["failed_chunks"][0]["reason"], "output_truncated")

    def test_has_chinese_leak(self):
        self.assertFalse(self.translator.has_chinese_leak("Bản dịch tiếng Việt."))
        self.assertTrue(self.translator.has_chinese_leak("Bản dịch chứa 奇迹种子魔法少女"))
        large_text = "Đoạn 1 tiếng Việt.\n\nĐoạn 2 chứa 奇迹种子魔法少女.\n\nĐoạn 3 tiếng Việt dài thật là dài để làm loãng tỷ lệ rò rỉ."
        self.assertTrue(self.translator.has_chinese_leak(large_text))

if __name__ == "__main__":
    unittest.main()
