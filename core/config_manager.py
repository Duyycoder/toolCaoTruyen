import os
import json
from typing import Optional, Dict
from sources.base import Color

DEFAULT_BASE_URL: str = "https://www.69shuba.com/txt"
DEFAULT_OUTPUT_DIR: str = "./truyen_tai_ve"
CONFIG_FILE: str = "config.json"

def get_default_config() -> Dict[str, any]:
    """Trả về cấu hình mặc định đầy đủ."""
    return {
        "base_url": DEFAULT_BASE_URL,
        "output_dir": DEFAULT_OUTPUT_DIR,
        "source": "69shuba",
        "translator": {
            "engine": "ollama",
            "ollama_model": "qwen2.5:7b-instruct",
            "leak_threshold_percent": 10,
            "gemini_api_key": "",
            "gemini_model": "gemini-flash-latest",
            "auto_extract_glossary": True
        }
    }

def load_config() -> Optional[Dict[str, any]]:
    """Đọc file config.json (nếu tồn tại) để lấy cấu hình lần chạy trước.
    Tự động migrate bổ sung field 'source' và 'translator' nếu thiếu.

    Returns:
        Dict chứa cấu hình hoặc None nếu không có file config.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if isinstance(config, dict):
                    modified = False
                    # Migration: nếu thiếu key 'source', tự động điền '69shuba'
                    if "source" not in config:
                        config["source"] = "69shuba"
                        modified = True
                    
                    # Migration: nếu thiếu key 'translator', tự động điền cấu hình mặc định
                    if "translator" not in config:
                        config["translator"] = get_default_config()["translator"]
                        modified = True
                    else:
                        # Điền các field còn thiếu trong block translator
                        default_trans = get_default_config()["translator"]
                        for key, val in default_trans.items():
                            if key not in config["translator"]:
                                config["translator"][key] = val
                                modified = True
                    
                    if modified:
                        save_full_config(config)
                    return config
        except (json.JSONDecodeError, IOError):
            return None
    return None

def save_config(base_url: str, output_dir: str, source: str) -> None:
    """Lưu cấu hình Base URL, Thư mục lưu file và Nguồn truyện vào config.json
    để tái sử dụng ở lần chạy sau. Bảo toàn các field khác như translator.

    Args:
        base_url: URL gốc của website truyện.
        output_dir: Đường dẫn thư mục lưu file.
        source: Tên nguồn truyện (ví dụ: '69shuba').
    """
    config = load_config()
    if config is None:
        config = get_default_config()
    
    config["base_url"] = base_url
    config["output_dir"] = output_dir
    config["source"] = source
    
    save_full_config(config)

def save_full_config(config: Dict[str, any]) -> None:
    """Lưu toàn bộ dict cấu hình vào file config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"{Color.YELLOW}[!] Không thể lưu config: {e}{Color.RESET}")

