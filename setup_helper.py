import os
import sys
import json

def initialize_gemini_api_files():
    gemini_api_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Gemini-API")
    os.makedirs(gemini_api_dir, exist_ok=True)
    
    cookies_path = os.path.join(gemini_api_dir, "cookies.json")
    default_cookies = {
        "__Secure-1PSID": "",
        "__Secure-1PSIDTS": ""
    }
    if not os.path.exists(cookies_path):
        try:
            with open(cookies_path, "w", encoding="utf-8") as f:
                json.dump(default_cookies, f, indent=2)
            print("[INFO] Đã tự động tạo file cookies.json mẫu tại Gemini-API/cookies.json")
        except Exception as e:
            print(f"[ERROR] Không thể tạo file cookies.json: {e}")

    api_keys_path = os.path.join(gemini_api_dir, "api_keys.json")
    default_api_keys = {
        "sk-gemini-YrVwXWGegzkFlevHPdQy7Fpry14HJVirqvnuxukz": "default"
    }
    if not os.path.exists(api_keys_path):
        try:
            with open(api_keys_path, "w", encoding="utf-8") as f:
                json.dump(default_api_keys, f, indent=2)
            print("[INFO] Đã tạo file api_keys.json mặc định tại Gemini-API/api_keys.json")
        except Exception as e:
            print(f"[ERROR] Không thể tạo file api_keys.json: {e}")

def main():
    # Khởi tạo các file cấu hình cho Gemini API trước
    initialize_gemini_api_files()
    
    if len(sys.argv) < 2:
        print("Usage: python setup_helper.py <engine> [gemini_key]")
        sys.exit(1)
        
    engine = sys.argv[1].strip()
    gemini_key = sys.argv[2].strip() if len(sys.argv) > 2 else ""
    
    config_file = "config.json"
    
    # Base structure
    config = {
        "base_url": "https://www.69shuba.com/txt",
        "output_dir": "./truyen_tai_ve",
        "source": "69shuba",
        "translator": {
            "engine": "ollama",
            "ollama_model": "qwen2.5:7b-instruct",
            "leak_threshold_percent": 10,
            "gemini_api_key": "",
            "gemini_model": "gemini-2.5-flash"
        }
    }
    
    # Load existing config if available
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    # Deep copy keys
                    for k, v in loaded.items():
                        if k == "translator" and isinstance(v, dict) and isinstance(config.get("translator"), dict):
                            config["translator"].update(v)
                        else:
                            config[k] = v
        except Exception as e:
            print(f"[WARN] Failed to load existing config.json: {e}")
            
    # Update values
    config["translator"]["engine"] = engine
    if gemini_key:
        config["translator"]["gemini_api_key"] = gemini_key
        
    # Write back
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"[OK] Successfully updated config.json: engine={engine}")
    except Exception as e:
        print(f"[ERROR] Failed to save config.json: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
