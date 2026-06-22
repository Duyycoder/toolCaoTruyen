from .ollama_translator import OllamaTranslator
from .gemini_translator import GeminiTranslator

TRANSLATOR_ENGINES = {
    "ollama": OllamaTranslator,
    "gemini": GeminiTranslator,
}

OLLAMA_MODELS = {
    "qwen2.5:7b-instruct": {
        "chunk_size_chars": 350,
        "label": "Qwen2.5 7B (Đã kiểm thử)"
    },
    "qwen3:8b": {
        "chunk_size_chars": 350,
        "label": "Qwen3 8B (Mới, chưa tối ưu riêng)"
    }
}
