import os
import sys
import json

def main():
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
