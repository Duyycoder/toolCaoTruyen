import os
import unittest
from unittest.mock import MagicMock
from translator.ollama_translator import OllamaTranslator
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
        
        # Có chữ Hán nhưng số lượng cực ít (dưới 5 ký tự) -> không cấu thành rò rỉ nghiêm trọng
        self.assertFalse(self.translator.contains_chinese_leak("Chương 9: 魔法"))

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
        def mock_call(text, is_title=False, source_lang="zh"):
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
        def mock_call(text, is_title=False, source_lang="zh"):
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
        def mock_call(text, is_title=False, source_lang="zh"):
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
        
        # Kiểm tra xem có chèn thẻ cảnh báo lỗi và giữ nguyên bản gốc không
        self.assertIn("> ⚠️ [Đoạn này AI dịch không thành công, giữ nguyên bản gốc]", result)
        self.assertIn("Văn bản bị lỗi.", result)

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

if __name__ == "__main__":
    unittest.main()
