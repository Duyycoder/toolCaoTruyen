import os
import json
from typing import Optional, Dict
from sources.base import Color

DEFAULT_BASE_URL: str = "https://www.69shuba.com/txt"
DEFAULT_OUTPUT_DIR: str = "./truyen_tai_ve"
CONFIG_FILE: str = "config.json"

def get_default_config() -> Dict[str, str]:
    """Trả về cấu hình mặc định đầy đủ."""
    return {
        "base_url": DEFAULT_BASE_URL,
        "output_dir": DEFAULT_OUTPUT_DIR,
        "source": "69shuba"
    }

def load_config() -> Optional[Dict[str, str]]:
    """Đọc file config.json (nếu tồn tại) để lấy cấu hình lần chạy trước.
    Tự động migrate bổ sung field 'source' nếu thiếu.

    Returns:
        Dict chứa cấu hình hoặc None nếu không có file config.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if isinstance(config, dict):
                    # Migration: nếu thiếu key 'source', tự động điền '69shuba'
                    if "source" not in config:
                        config["source"] = "69shuba"
                        # Ghi lại config đã migrate vào file để đồng bộ
                        save_config(
                            config.get("base_url", DEFAULT_BASE_URL),
                            config.get("output_dir", DEFAULT_OUTPUT_DIR),
                            "69shuba"
                        )
                    return config
        except (json.JSONDecodeError, IOError):
            return None
    return None

def save_config(base_url: str, output_dir: str, source: str) -> None:
    """Lưu cấu hình Base URL, Thư mục lưu file và Nguồn truyện vào config.json
    để tái sử dụng ở lần chạy sau.

    Args:
        base_url: URL gốc của website truyện.
        output_dir: Đường dẫn thư mục lưu file.
        source: Tên nguồn truyện (ví dụ: '69shuba').
    """
    config = {
        "base_url": base_url,
        "output_dir": output_dir,
        "source": source,
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"{Color.YELLOW}[!] Không thể lưu config: {e}{Color.RESET}")
