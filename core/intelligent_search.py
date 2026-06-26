"""
core/intelligent_search.py
Module dịch thuật và suy luận tên truyện thông minh bằng LLM.
"""
import json
import urllib.request
import re
from core.config_manager import load_config
from sources.base import Color

def call_llm_raw(prompt: str, system_prompt: str = "", response_json: bool = False) -> str:
    """Gọi trực tiếp LLM theo config hiện tại (Ollama, Gemini, Gemini Proxy)."""
    config = load_config()
    if not config or "translator" not in config:
        raise ValueError("Chưa cấu hình translator trong config.json")
        
    t_cfg = config["translator"]
    engine_type = t_cfg.get("engine", "ollama")
    
    if engine_type == "ollama":
        ollama_model = t_cfg.get("ollama_model", "qwen2.5:7b-instruct")
        api_url = "http://localhost:11434/api/chat"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.3
            }
        }
        if response_json:
            payload["format"] = "json"
            
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("message", {}).get("content", "").strip()
            
    elif engine_type == "gemini":
        gemini_api_key = t_cfg.get("gemini_api_key", "")
        gemini_model = t_cfg.get("gemini_model", "gemini-flash-latest")
        if not gemini_api_key:
            raise ValueError("Chưa cấu hình gemini_api_key")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_api_key}"
        
        contents = [{
            "parts": [{"text": prompt}]
        }]
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }
        if response_json:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
            raise ValueError(f"Gemini API returned empty response: {res_data}")
            
    elif engine_type == "gemini_api":
        gemini_offline_key = t_cfg.get("gemini_offline_key", "")
        gemini_offline_base_url = t_cfg.get("gemini_offline_base_url", "http://localhost:7860/v1").rstrip("/")
        gemini_offline_model = t_cfg.get("gemini_offline_model", "gemini-2.5-flash")
        
        api_url = f"{gemini_offline_base_url}/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": gemini_offline_model,
            "messages": messages,
            "temperature": 0.3
        }
        if response_json:
            payload["response_format"] = {"type": "json_object"}
            
        headers = {"Content-Type": "application/json"}
        if gemini_offline_key:
            headers["Authorization"] = f"Bearer {gemini_offline_key}"
            
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            choices = res_data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            raise ValueError(f"Gemini Proxy returned empty response: {res_data}")
            
    else:
        raise ValueError(f"Không hỗ trợ engine: {engine_type}")

def translate_query_to_chinese(query: str) -> str:
    """Dịch tên truyện từ tiếng Việt/Hán Việt sang tên tiếng Trung gốc."""
    # Nếu không chứa ký tự Latin nào thì coi như đã nhập tiếng Trung rồi
    if not re.search(r'[a-zA-ZáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđĐ]', query):
        return query
        
    system_prompt = (
        "You are a translation assistant specializing in web novel titles. "
        "Your task is to translate the Vietnamese/Hán-Việt novel title into its original Chinese name. "
        "Respond ONLY with the translated Chinese title. Do not include any explanations, punctuation, or extra characters."
    )
    prompt = (
        f"Translate the following novel title to Chinese: '{query}'\n"
        f"Examples:\n"
        f"- Đấu La Đại Lục -> 斗罗大陆\n"
        f"- Mục Thần Ký -> 牧神记\n"
        f"- Thiên Khải Chi Môn -> 天启之门\n"
        f"- Ta có một ngôi nhà kinh dị -> 我有一座恐怖屋\n"
        f"- Toàn chức pháp sư -> 全职法师\n"
        f"Title: {query}"
    )
    try:
        translated = call_llm_raw(prompt, system_prompt=system_prompt)
        # Clean up any potential markdown or extra quotes
        translated = re.sub(r'["\'\s]', '', translated)
        return translated
    except Exception as e:
        print(f"{Color.YELLOW}[WARN] Lỗi dịch truy vấn: {e}. Dùng truy vấn gốc.{Color.RESET}")
        return query

def generate_alternative_chinese_names(query: str, failed_attempts: list[str]) -> list[str]:
    """Sử dụng LLM để phân tích và sinh ra các tên tiếng Trung thay thế dựa trên lịch sử thất bại."""
    system_prompt = (
        "You are an expert in Chinese web novels and translation. "
        "The user wants to find a Chinese novel on a book site. They searched for some terms, but no books were found.\n"
        "Your job is to reason about what the actual Chinese name might be. Consider Hán-Việt characters, Pinyin transliteration, synonyms, typos, abbreviation, English titles, or related phrasing.\n"
        "Generate a JSON array of alternative Chinese titles (exactly 5 alternative search terms)."
    )
    prompt = (
        f"Original query: '{query}'\n"
        f"Failed search terms so far: {json.dumps(failed_attempts, ensure_ascii=False)}\n\n"
        f"Please think step by step about different possible Chinese translations or synonyms for the original query, "
        f"avoiding the failed search terms. Return a JSON object with a single key 'alternatives' containing a list of exactly 5 Chinese strings. "
        f"Example output structure: {{\"alternatives\": [\"天启之门\", \"启迪之门\", \"天启\", \"天之启\", \"Thien Khai Chi Mon\"]}}"
    )
    try:
        response_text = call_llm_raw(prompt, system_prompt=system_prompt, response_json=True)
        # Clean up markdown block if returned
        if response_text.startswith("```json"): response_text = response_text[7:]
        if response_text.startswith("```"): response_text = response_text[3:]
        if response_text.endswith("```"): response_text = response_text[:-3]
        response_text = response_text.strip()
        
        data = json.loads(response_text)
        alternatives = data.get("alternatives", [])
        return [str(alt).strip() for alt in alternatives if alt]
    except Exception as e:
        print(f"{Color.YELLOW}[WARN] Lỗi sinh tên truyện thay thế: {e}{Color.RESET}")
        return []
