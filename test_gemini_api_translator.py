import unittest
from unittest.mock import MagicMock, patch
import json
import urllib.error
from translator.gemini_api_translator import GeminiApiTranslator
from translator.gemini_translator import GeminiSafetyBlockError

class TestGeminiApiTranslator(unittest.TestCase):
    def setUp(self):
        self.translator = GeminiApiTranslator(
            api_key="sk-test-key",
            base_url="http://localhost:7860/v1",
            model="gemini-2.5-flash",
            leak_threshold_percent=10.0
        )

    def test_is_available(self):
        self.assertTrue(self.translator.is_available())
        
        empty_key_translator = GeminiApiTranslator(api_key="", base_url="http://localhost:7860/v1")
        self.assertFalse(empty_key_translator.is_available())

        empty_url_translator = GeminiApiTranslator(api_key="key", base_url="")
        self.assertFalse(empty_url_translator.is_available())

    @patch("urllib.request.urlopen")
    def test_execute_api_call_success(self, mock_urlopen):
        # Giả lập response từ API OpenAI-compatible
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [
                {
                    "message": {
                        "content": "Bản dịch tiếng Việt thành công"
                    },
                    "finish_reason": "stop"
                }
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Payload định dạng Gemini gửi vào
        payload = {
            "contents": [{"parts": [{"text": "Hello"}]}],
            "systemInstruction": {"parts": [{"text": "Dịch sang tiếng Việt"}]},
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 100}
        }

        result = self.translator._execute_api_call(None, payload)
        self.assertEqual(result, "Bản dịch tiếng Việt thành công")
        self.assertEqual(self.translator.last_finish_reason, "stop")

    @patch("urllib.request.urlopen")
    def test_execute_api_call_safety_block(self, mock_urlopen):
        # Giả lập phản hồi bị chặn vì chính sách an toàn
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [
                {
                    "message": {
                        "content": ""
                    },
                    "finish_reason": "content_filter"
                }
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        payload = {
            "contents": [{"parts": [{"text": "Nội dung nhạy cảm"}]}]
        }

        with self.assertRaises(GeminiSafetyBlockError):
            self.translator._execute_api_call(None, payload)

if __name__ == "__main__":
    unittest.main()
