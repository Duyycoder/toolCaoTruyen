from .ollama_translator import OllamaTranslator
from .gemini_translator import GeminiTranslator
from .gemini_api_translator import GeminiApiTranslator

TRANSLATOR_ENGINES = {
    "ollama": OllamaTranslator,
    "gemini": GeminiTranslator,
    "gemini_api": GeminiApiTranslator,
}

OLLAMA_MODELS = {
    # --- Model CHUYÊN DỊCH (Machine Translation) ---
    # prompt_style != "chat": dùng template dịch thuật cố định của model,
    # không system prompt/few-shot; glossary chèn qua template thuật ngữ.
    "hy-mt2:1.8b": {
        "prompt_style": "hunyuan_mt",
        "chunk_size_chars": 500,
        "num_ctx": 2048,
        "temperature": 0.7,
        "top_p": 0.6,
        "top_k": 20,
        "repeat_penalty": 1.05,
        "label": "HY-MT2 1.8B — chuyên dịch Trung/Anh→Việt, siêu nhẹ (khuyến nghị)"
    },
    "translategemma:4b": {
        "prompt_style": "translategemma",
        "chunk_size_chars": 500,
        "num_ctx": 2048,
        "temperature": 0.7,
        "top_p": 0.6,
        "top_k": 20,
        "repeat_penalty": 1.05,
        "label": "TranslateGemma 4B (Google) — chuyên dịch, 55 ngôn ngữ"
    },
    # --- Model chat tổng quát ---
    "qwen2.5:7b-instruct": {
        "chunk_size_chars": 350,
        # 2048 đủ cho system prompt + glossary + chunk 350 chars + output,
        # tiết kiệm ~50% VRAM KV cache so với 4096 (quan trọng với GPU 6GB)
        "num_ctx": 2048,
        "label": "Qwen2.5 7B (Đã kiểm thử)"
    },
    "qwen3:8b": {
        "chunk_size_chars": 400,
        "temperature": 0.05,
        "few_shot": True,
        "num_ctx": 2560,  # có few-shot nên prompt dài hơn qwen2.5
        "label": "Qwen3 8B (Đã tối ưu giảm leak)"
    }
}
