from .ollama_translator import OllamaTranslator
from .gemini_translator import GeminiTranslator
from .gemini_api_translator import GeminiApiTranslator

TRANSLATOR_ENGINES = {
    "ollama": OllamaTranslator,
    "gemini": GeminiTranslator,
    "gemini_api": GeminiApiTranslator,
}

OLLAMA_MODELS = {
    "qwen2.5:7b-instruct": {
        "chunk_size_chars": 350,
        "label": "Qwen2.5 7B (Đã kiểm thử)"
    },
    "qwen3:8b": {
        "chunk_size_chars": 400,
        "temperature": 0.05,
        "few_shot": True,
        "label": "Qwen3 8B (Đã tối ưu giảm leak)"
    }
}
