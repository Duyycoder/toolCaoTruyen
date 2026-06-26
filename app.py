import os
import sys
import asyncio
import webbrowser
import json
import re
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Thêm thư mục hiện tại vào sys.path để python nhận diện core và sources
sys.path.insert(0, ".")

from sources.registry import SOURCES, get_source
from core.config_manager import load_config, save_config, get_default_config, save_full_config
from core.crawler_engine import download_chapters

app = FastAPI(title="Tool Cào Truyện Web UI")

import subprocess
import sys
import atexit
import signal
from urllib.parse import urlparse

# Global variables for Gemini API subprocess management
gemini_api_process = None
active_heartbeats = set()
heartbeat_timeout_task = None

def initialize_gemini_api_files():
    gemini_api_dir = os.path.join(os.getcwd(), "Gemini-API")
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

def check_gemini_cookies() -> dict:
    cookies_path = os.path.join("Gemini-API", "cookies.json")
    if not os.path.exists(cookies_path):
        initialize_gemini_api_files()
        return {"status": "missing", "message": "Không tìm thấy file cookies.json. File mẫu đã được tự động tạo tại Gemini-API/cookies.json."}
        
    try:
        with open(cookies_path, "r", encoding="utf-8") as f:
            content = json.load(f)
        if not isinstance(content, dict):
            return {"status": "invalid", "message": "File cookies.json có định dạng không hợp lệ. Vui lòng kiểm tra lại."}
        
        psid = content.get("__Secure-1PSID", "").strip()
        psidts = content.get("__Secure-1PSIDTS", "").strip()
        
        if not psid or not psidts:
            return {"status": "empty", "message": "Bạn chưa cấu hình cookies trong Gemini-API/cookies.json. Vui lòng điền __Secure-1PSID và __Secure-1PSIDTS."}
            
        return {"status": "ready"}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi khi đọc file cookies.json: {str(e)}"}

def get_gemini_api_port() -> int:
    try:
        config = load_config()
        if config and "translator" in config:
            base_url = config["translator"].get("gemini_offline_base_url", "http://localhost:7860/v1")
            parsed = urlparse(base_url)
            if parsed.port:
                return parsed.port
    except Exception:
        pass
    return 7860

def kill_gemini_api_server():
    global gemini_api_process
    if gemini_api_process:
        print("[*] Đang tắt Gemini API Server...")
        try:
            gemini_api_process.terminate()
            gemini_api_process.wait(timeout=3)
            print("[✓] Đã tắt Gemini API Server.")
        except subprocess.TimeoutExpired:
            print("[WARN] Gemini API Server không phản hồi, tiến hành force kill...")
            try:
                gemini_api_process.kill()
            except Exception:
                pass
        except Exception as e:
            print(f"[✗] Lỗi khi tắt Gemini API Server: {e}")
        finally:
            gemini_api_process = None

@app.on_event("startup")
def startup_event():
    global gemini_api_process
    
    # 1. Khởi tạo và kiểm tra cookies
    initialize_gemini_api_files()
    cookie_status = check_gemini_cookies()
    if cookie_status["status"] != "ready":
        print(f"\n============================================================")
        print(f"⚠️  CANH BAO: {cookie_status['message']}")
        print(f"============================================================\n")
        
    # 2. Khởi chạy Gemini API Server làm tiến trình con (subprocess)
    gemini_dir = os.path.join(os.getcwd(), "Gemini-API")
    if os.path.exists(gemini_dir):
        python_exe = sys.executable
        port = get_gemini_api_port()
        print(f"[*] Đang khởi chạy Gemini API Server ở terminal riêng (Cổng: {port})...")
        
        env = os.environ.copy()
        env["PYTHONPATH"] = gemini_dir
        env["PYTHONIOENCODING"] = "utf-8"
        
        try:
            gemini_api_process = subprocess.Popen(
                [python_exe, "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", str(port)],
                cwd=gemini_dir,
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            print(f"[✓] Đã kích hoạt terminal chạy Gemini API Server (PID: {gemini_api_process.pid})")
        except Exception as e:
            print(f"[✗] Không thể khởi chạy Gemini API Server: {e}")

@app.on_event("shutdown")
def shutdown_event():
    kill_gemini_api_server()

# Sử dụng atexit để đảm bảo kill tiến trình khi tắt
atexit.register(kill_gemini_api_server)

async def shutdown_server_after_delay():
    await asyncio.sleep(5.0)  # Chờ 5 giây để tránh F5 reload trang
    if len(active_heartbeats) == 0:
        print("[*] Đóng trình duyệt: Không phát hiện tab Web UI hoạt động. Đang tự động tắt ứng dụng...")
        kill_gemini_api_server()
        import os
        os.kill(os.getpid(), signal.SIGINT)

@app.websocket("/ws/heartbeat")
async def websocket_heartbeat(websocket: WebSocket):
    global heartbeat_timeout_task
    await websocket.accept()
    
    # Hủy task tắt máy nếu có kết nối mới trong 5s
    if heartbeat_timeout_task and not heartbeat_timeout_task.done():
        heartbeat_timeout_task.cancel()
        
    active_heartbeats.add(websocket)
    try:
        while True:
            # Lắng nghe tin nhắn duy trì
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        active_heartbeats.remove(websocket)
        if len(active_heartbeats) == 0:
            # Không còn kết nối nào, lập lịch tắt máy
            heartbeat_timeout_task = asyncio.create_task(shutdown_server_after_delay())

@app.get("/api/check-gemini-cookies")
async def api_check_gemini_cookies():
    return check_gemini_cookies()

def sanitize_filename(name: str) -> str:
    # Thay thế các ký tự cấm trên Windows bằng khoảng trắng
    name = re.sub(r'[\\/*?:"<>|]', " ", name)
    # Loại bỏ khoảng trắng thừa
    name = re.sub(r'\s+', " ", name).strip()
    return name

async def translate_filename_fn(filename: str, translator) -> str:
    base_name, ext = os.path.splitext(filename)
    if ext.lower() != ".md":
        return filename
        
    # Tìm prefix số (ví dụ: "0001_", "1.", "Chương 1 - ")
    match = re.match(r"^(\d+[_.-]?\s*|Chapter\s*\d+[_.-]?\s*|Chương\s*\d+[_.-]?\s*)(.*)$", base_name, re.IGNORECASE)
    if match:
        prefix = match.group(1)
        title_to_translate = match.group(2).strip()
    else:
        prefix = ""
        title_to_translate = base_name.strip()
        
    if not title_to_translate:
        return filename
        
    # Chỉ dịch nếu tên file chứa ký tự Trung Quốc (Hán) để tránh mô hình ảo hóa
    if not re.search(r"[\u4e00-\u9fff]", title_to_translate):
        return filename
        
    try:
        # Dịch nhanh tiêu đề bằng translator. Chạy đồng bộ trong thread pool.
        translated = await asyncio.to_thread(translator.translate, title_to_translate)
        # Loại bỏ các tag cảnh báo nếu có
        translated = re.sub(r"> ⚠️ \[Đoạn này AI dịch không thành công.*\]", "", translated).strip()
        # Loại bỏ các dòng trống hoặc dòng bắt đầu bằng >
        translated_lines = []
        for line in translated.split("\n"):
            line = line.strip()
            if line and not line.startswith(">"):
                translated_lines.append(line)
        translated = " ".join(translated_lines)
        
        sanitized = sanitize_filename(translated)
        if len(sanitized) > 80:
            sanitized = sanitized[:80].strip()
        if sanitized:
            return f"{prefix}{sanitized}{ext}"
    except Exception as e:
        print(f"[WARN] Không thể dịch tên file '{filename}': {e}")
        
    return filename

class ConfigModel(BaseModel):
    base_url: str
    output_dir: str
    source: str

class TranslatorConfigModel(BaseModel):
    engine: str
    ollama_model: str
    leak_threshold_percent: int
    gemini_api_key: str
    gemini_model: str
    gemini_offline_key: Optional[str] = ""
    gemini_offline_base_url: Optional[str] = "http://localhost:7860/v1"
    gemini_offline_model: Optional[str] = "gemini-2.5-flash"
    auto_extract_glossary: Optional[bool] = True
    genre: Optional[str] = "tien_hiep"

# Endpoint trả về trang HTML chính
@app.get("/", response_class=HTMLResponse)
async def read_index():
    template_path = os.path.join("web", "templates", "index.html")
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

# API 1: Lấy danh sách nguồn truyện
@app.get("/api/sources")
async def get_sources():
    return {"sources": list(SOURCES.keys())}

# API 2: Lấy cấu hình hiện tại
@app.get("/api/config")
async def get_config():
    config = load_config()
    if not config:
        config = get_default_config()
    return config

# API 3: Lưu cấu hình mới của crawler
@app.post("/api/config")
async def update_config(config: ConfigModel):
    try:
        save_config(config.base_url, config.output_dir, config.source)
        return {"status": "success", "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu cấu hình: {str(e)}")

# API 3b: Lưu cấu hình dịch thuật
@app.post("/api/config/translator")
async def update_translator_config(trans_config: TranslatorConfigModel):
    try:
        config = load_config()
        if not config:
            config = get_default_config()
        config["translator"] = trans_config.dict()
        save_full_config(config)
        return {"status": "success", "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu cấu hình dịch: {str(e)}")

# API 3c: Lấy danh sách các ngôn ngữ dịch hỗ trợ
@app.get("/api/languages")
async def get_languages():
    from translator import SUPPORTED_LANGUAGES
    return {"languages": SUPPORTED_LANGUAGES}

# API 3d: Lấy danh sách model Ollama được định nghĩa
@app.get("/api/ollama/models")
async def get_ollama_models_registry():
    from translator.registry import OLLAMA_MODELS
    import urllib.request
    import json
    
    # Truy vấn Ollama để tự động nạp các model local đã cài đặt
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
            local_models = data.get("models", [])
            for m in local_models:
                name = m.get("name")
                if name:
                    # Đăng ký model nếu chưa tồn tại vào registry toàn cục
                    if name not in OLLAMA_MODELS:
                        OLLAMA_MODELS[name] = {
                            "chunk_size_chars": 400,
                            "temperature": 0.05,
                            "few_shot": True,
                            "label": f"Local Model: {name}"
                        }
                    # Đăng ký cả phiên bản ngắn của tên model (không có :latest)
                    short_name = name.split(":")[0] if ":" in name else name
                    if short_name and short_name not in OLLAMA_MODELS:
                        OLLAMA_MODELS[short_name] = {
                            "chunk_size_chars": 400,
                            "temperature": 0.05,
                            "few_shot": True,
                            "label": f"Local Model: {short_name}"
                        }
    except Exception as e:
        print(f"[Warning] Không thể quét models từ Ollama local: {e}")
        
    return {"models": OLLAMA_MODELS}

# API 3e: Kiểm tra xem một model Ollama đã được tải chưa
@app.get("/api/ollama/check-model")
async def check_ollama_model(model: str):
    try:
        from translator import OllamaTranslator
        translator = OllamaTranslator(model=model)
        available = translator.is_available()
        return {"model": model, "available": available}
    except Exception as e:
        return {"model": model, "available": False, "error": str(e)}


# API 3f: Tìm kiếm truyện theo tên
@app.get("/api/search")
async def search_book_api(keyword: str, source: str = "69shuba"):
    """Tìm kiếm truyện theo tên qua API, hỗ trợ dịch tự động."""
    from sources.book_search import BookSearcher
    from core.intelligent_search import translate_query_to_chinese
    
    def _do_search():
        base_url = "https://www.69shuba.com/txt"  # default
        # Lấy base_url từ config hiện tại nếu có
        from core.config_manager import load_config
        config = load_config()
        if config:
            base_url = config.get("base_url", base_url)
            
        parser = get_source(source, base_url)
        
        # Tự động dịch sang tiếng Trung nếu là tiếng Việt
        translated_keyword = translate_query_to_chinese(keyword)
        
        with BookSearcher(parser) as searcher:
            results = searcher.search(translated_keyword)
            # Thử lại bằng tên thay thế nếu rỗng (1 lần thử để tối ưu thời gian phản hồi API)
            if not results:
                from core.intelligent_search import generate_alternative_chinese_names
                alternatives = generate_alternative_chinese_names(keyword, [keyword, translated_keyword])
                for alt in alternatives:
                    results = searcher.search(alt)
                    if results:
                        break
            return results, translated_keyword
            
    try:
        results, used_keyword = await asyncio.to_thread(_do_search)
        return {
            "status": "success",
            "keyword_used": used_keyword,
            "results": [
                {
                    "book_id": r.book_id,
                    "title": r.title,
                    "author": r.author,
                    "book_url": r.book_url,
                    "status": r.status,
                    "latest_chapter": r.latest_chapter,
                } for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tìm kiếm: {str(e)}")


# API 3g: Lấy mục lục chương
@app.get("/api/catalog")
async def get_catalog_api(book_url: str, source: str = "69shuba"):
    """Lấy mục lục chương qua API."""
    from sources.book_search import BookSearcher
    
    def _do_catalog():
        base_url = "https://www.69shuba.com/txt"
        from core.config_manager import load_config
        config = load_config()
        if config:
            base_url = config.get("base_url", base_url)
            
        parser = get_source(source, base_url)
        with BookSearcher(parser) as searcher:
            return searcher.get_catalog(book_url)
            
    try:
        chapters = await asyncio.to_thread(_do_catalog)
        return {
            "status": "success",
            "total_chapters": len(chapters),
            "chapters": [
                {
                    "chapter_id": ch.chapter_id,
                    "title": ch.title,
                    "chapter_url": ch.chapter_url,
                    "index": ch.index,
                } for ch in chapters
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lấy mục lục: {str(e)}")


# API 4: Chọn thư mục bằng Dialog hệ thống (Tkinter)
def ask_directory_sync() -> str:
    import tkinter as tk
    from tkinter import filedialog
    
    # Khởi tạo Tkinter root ẩn
    root = tk.Tk()
    root.withdraw()
    # Đẩy cửa sổ dialog lên trên cùng các cửa sổ khác
    root.attributes('-topmost', True)
    
    selected_dir = filedialog.askdirectory(parent=root, title="Chọn thư mục lưu truyện")
    root.destroy()
    return selected_dir

@app.get("/api/select-directory")
async def select_directory():
    try:
        # Chạy đồng bộ trong thread pool của asyncio để tránh làm nghẽn Event Loop
        selected_dir = await asyncio.to_thread(ask_directory_sync)
        if selected_dir:
            return {"status": "success", "path": os.path.abspath(selected_dir)}
        return {"status": "cancelled", "path": ""}
    except Exception as e:
        return {"status": "error", "message": f"Không thể mở dialog: {str(e)}"}

# WebSocket Endpoint: Điều khiển cào truyện real-time
@app.websocket("/ws/crawl")
async def websocket_crawl(websocket: WebSocket):
    await websocket.accept()
    
    main_loop = asyncio.get_running_loop()
    stopped = False

    # Định nghĩa callback gửi dữ liệu qua WebSocket
    def ws_progress_callback(event_data: dict) -> None:
        message = json.dumps(event_data, ensure_ascii=False)
        # Sử dụng run_coroutine_threadsafe để đẩy tác vụ gửi tin nhắn về Event Loop chính từ Thread của Crawler
        asyncio.run_coroutine_threadsafe(
            websocket.send_text(message),
            main_loop
        )

    def is_stopped_check() -> bool:
        return stopped

    # Task lắng nghe tin nhắn từ Client (lệnh dừng)
    async def listen_for_client_messages():
        nonlocal stopped
        try:
            async for message in websocket.iter_text():
                try:
                    data = json.loads(message)
                    if data.get("command") == "stop":
                        stopped = True
                        # Thông báo phản hồi lệnh dừng
                        await websocket.send_json({
                            "event": "stopped_request",
                            "message": "[i] Đang gửi yêu cầu dừng tới crawler..."
                        })
                        break
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            stopped = True
        except Exception:
            stopped = True

    # Nhận cấu hình khởi chạy từ client
    try:
        start_msg = await websocket.receive_text()
        config = json.loads(start_msg)
        
        # Trích xuất các thông số cấu hình
        base_url = config.get("base_url")
        num_chapters = int(config.get("num_chapters"))
        output_dir = config.get("output_dir")
        source = config.get("source")

        # Hỗ trợ chế độ dán URL trực tiếp: nếu story_id là URL, giữ nguyên dạng string
        raw_story_id = config.get("story_id", "")
        raw_start_chapter_id = config.get("start_chapter_id", "")

        if isinstance(raw_story_id, str) and raw_story_id.startswith("http"):
            story_id = raw_story_id
            start_chapter_id = raw_story_id
        else:
            story_id = int(raw_story_id)
            start_chapter_id = int(raw_start_chapter_id)

        # Khởi tạo parser tương ứng
        parser = get_source(source, base_url)

        # Chạy luồng lắng nghe lệnh dừng song song
        listen_task = asyncio.create_task(listen_for_client_messages())

        # Thực thi crawl trong thread pool riêng (vì download_chapters là blocking và dùng Selenium)
        try:
            await asyncio.to_thread(
                download_chapters,
                base_url=base_url,
                story_id=story_id,
                start_chapter_id=start_chapter_id,
                num_chapters=num_chapters,
                output_dir=output_dir,
                parser=parser,
                progress_callback=ws_progress_callback,
                is_stopped=is_stopped_check
            )
        finally:
            # Hủy task lắng nghe khi luồng cào kết thúc
            listen_task.cancel()
            
    except WebSocketDisconnect:
        stopped = True
    except Exception as e:
        # Gửi thông tin lỗi nếu có sự cố
        try:
            await websocket.send_json({
                "event": "error",
                "message": f"[✗] Lỗi hệ thống: {str(e)}"
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

# API 5: Chọn nhiều file .md bằng Dialog hệ thống (Tkinter)
def ask_files_sync() -> List[str]:
    import tkinter as tk
    from tkinter import filedialog
    
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    selected_files = filedialog.askopenfilenames(
        parent=root,
        title="Chọn các file Markdown (.md) để dịch",
        filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
    )
    root.destroy()
    return list(selected_files)

@app.get("/api/select-files")
async def select_files():
    try:
        selected_files = await asyncio.to_thread(ask_files_sync)
        if selected_files:
            return {"status": "success", "files": [os.path.abspath(f) for f in selected_files]}
        return {"status": "cancelled", "files": []}
    except Exception as e:
        return {"status": "error", "message": f"Không thể mở dialog chọn file: {str(e)}"}

# WebSocket Endpoint: Điều khiển dịch truyện real-time
@app.websocket("/ws/translate")
async def websocket_translate(websocket: WebSocket):
    await websocket.accept()
    
    main_loop = asyncio.get_running_loop()
    stopped = False

    # Định nghĩa callback gửi log thô về client
    def ws_log_callback(msg: str) -> None:
        asyncio.run_coroutine_threadsafe(
            websocket.send_json({"event": "log", "message": msg}),
            main_loop
        )

    # Task lắng nghe lệnh dừng từ Client
    async def listen_for_client_messages():
        nonlocal stopped
        try:
            async for message in websocket.iter_text():
                try:
                    data = json.loads(message)
                    if data.get("command") == "stop":
                        stopped = True
                        await websocket.send_json({
                            "event": "stopped_request",
                            "message": "[i] Đang gửi yêu cầu dừng tới translator..."
                        })
                        break
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            stopped = True
        except Exception:
            stopped = True

    try:
        # Nhận cấu hình từ client
        start_msg = await websocket.receive_text()
        config = json.loads(start_msg)
        
        file_paths = config.get("file_paths", [])
        folder_path = config.get("folder_path", "")
        engine_type = config.get("engine", "ollama")
        ollama_model = config.get("ollama_model", "qwen2.5:7b-instruct")
        gemini_api_key = config.get("gemini_api_key", "")
        gemini_model = config.get("gemini_model", "gemini-2.5-flash")
        gemini_offline_key = config.get("gemini_offline_key", "")
        gemini_offline_base_url = config.get("gemini_offline_base_url", "http://localhost:7860/v1")
        gemini_offline_model = config.get("gemini_offline_model", "gemini-2.5-flash")
        leak_threshold = int(config.get("leak_threshold_percent", 10))
        output_dir_custom = config.get("output_dir", "").strip()
        auto_extract_glossary = config.get("auto_extract_glossary", True)
        genre = config.get("genre", "tien_hiep")
        
        # Thu nhập danh sách file dịch và xác định thư mục truyện
        files_to_translate = []
        story_dir = ""
        if file_paths:
            files_to_translate = [os.path.abspath(f) for f in file_paths]
            if files_to_translate:
                story_dir = os.path.dirname(files_to_translate[0])
        elif folder_path:
            folder_abs = os.path.abspath(folder_path)
            if os.path.exists(folder_abs) and os.path.isdir(folder_abs):
                story_dir = folder_abs
                for entry in sorted(os.listdir(folder_abs)):
                    if entry.endswith(".md"):
                        files_to_translate.append(os.path.join(folder_abs, entry))
        
        if not files_to_translate:
            await websocket.send_json({
                "event": "error",
                "message": "[✗] Không tìm thấy file .md nào để dịch."
            })
            return

        await websocket.send_json({
            "event": "start",
            "total_files": len(files_to_translate),
            "message": f"[+] Tìm thấy {len(files_to_translate)} file để tiến hành dịch."
        })

        # Khởi tạo GlossaryManager và nạp từ điển
        from translator.glossary_manager import GlossaryManager
        glossary_mgr = GlossaryManager(root_dir=".")
        if story_dir:
            glossary_mgr.load_story_glossary(story_dir)
            combined_glossary = glossary_mgr.get_combined_glossary()
            glossary_info_msg = f"[+] Đã tải glossary của truyện từ {os.path.basename(story_dir)} (Tổng cộng: {len(combined_glossary)} từ)."
        else:
            combined_glossary = glossary_mgr.global_glossary
            glossary_info_msg = f"[+] Đã tải global glossary (Tổng cộng: {len(combined_glossary)} từ)."

        await websocket.send_json({
            "event": "log",
            "message": glossary_info_msg
        })

        # Khởi tạo Engine tương ứng
        from translator import TRANSLATOR_ENGINES, OLLAMA_MODELS
        
        # Khởi tạo gemini_extractor độc lập nếu có api_key để hỗ trợ trích xuất glossary
        gemini_extractor = None
        if gemini_api_key and gemini_api_key.strip():
            try:
                gemini_extractor = TRANSLATOR_ENGINES["gemini"](
                    api_key=gemini_api_key,
                    model=gemini_model,
                    leak_threshold_percent=leak_threshold
                )
            except Exception as e:
                await websocket.send_json({
                    "event": "log",
                    "message": f"[WARN] Không thể khởi tạo gemini_extractor độc lập: {e}"
                })

        if engine_type == "ollama":
            chunk_size = OLLAMA_MODELS.get(ollama_model, {}).get("chunk_size_chars", 350)
            translator = TRANSLATOR_ENGINES["ollama"](
                model=ollama_model,
                max_chunk_chars=chunk_size,
                leak_threshold_percent=leak_threshold
            )
        elif engine_type == "gemini":
            if gemini_extractor:
                translator = gemini_extractor
            else:
                translator = TRANSLATOR_ENGINES["gemini"](
                    api_key=gemini_api_key,
                    model=gemini_model,
                    leak_threshold_percent=leak_threshold
                )
        elif engine_type == "gemini_api":
            translator = TRANSLATOR_ENGINES["gemini_api"](
                api_key=gemini_offline_key,
                base_url=gemini_offline_base_url,
                model=gemini_offline_model,
                leak_threshold_percent=leak_threshold
            )
        else:
            await websocket.send_json({
                "event": "error",
                "message": f"[✗] Nguồn dịch '{engine_type}' không hợp lệ."
            })
            return

        # Cấu hình Genre cho các translator
        translator.set_genre(genre)
        if gemini_extractor:
            gemini_extractor.set_genre(genre)
            
        # Nạp từ điển thành ngữ dùng chung (common_idioms.json)
        common_idioms_path = os.path.join(".", "common_idioms.json")
        if os.path.exists(common_idioms_path):
            try:
                with open(common_idioms_path, 'r', encoding='utf-8') as f:
                    common_idioms = json.load(f)
                    translator.set_common_idioms(common_idioms)
                    if gemini_extractor:
                        gemini_extractor.set_common_idioms(common_idioms)
            except Exception as e:
                await websocket.send_json({
                    "event": "log",
                    "message": f"[WARN] Không thể nạp từ điển thành ngữ chung: {e}"
                })

        # Nạp từ điển vào translator
        translator.set_glossary(combined_glossary)

        # Chạy task lắng nghe dừng song song
        listen_task = asyncio.create_task(listen_for_client_messages())

        # Vòng lặp xử lý từng file
        for idx, file_path in enumerate(files_to_translate, 1):
            if stopped:
                break
                
            # Nghỉ 2.0s trước khi dịch file tiếp theo (ngoài file đầu tiên) để tránh spam API
            if idx > 1:
                await asyncio.sleep(2.0)
                
            file_name = os.path.basename(file_path)
            
            # Dịch tên file
            await websocket.send_json({
                "event": "log",
                "message": f"[->] Đang dịch tên file '{file_name}'..."
            })
            translated_file_name = await translate_filename_fn(file_name, translator)
            if translated_file_name != file_name:
                await websocket.send_json({
                    "event": "log",
                    "message": f"[✓] Tên file mới: '{translated_file_name}'"
                })
            
            await websocket.send_json({
                "event": "file_start",
                "index": idx,
                "file_name": translated_file_name,
                "message": f"\n[***] Bắt đầu dịch file {idx}/{len(files_to_translate)}: {file_name} -> {translated_file_name}"
            })

            file_dir = os.path.dirname(file_path)
            output_dir = os.path.abspath(output_dir_custom) if output_dir_custom else os.path.join(file_dir, "dich")
            output_path = os.path.join(output_dir, translated_file_name)

            try:
                def run_translation_file():
                    # 1. Tự động trích xuất từ mới từ 1500 ký tự đầu tiên của chương
                    if auto_extract_glossary:
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                text_content = f.read()
                            
                            if text_content.strip():
                                # Chọn extractor phù hợp: Ưu tiên gemini_extractor nếu khả dụng, nếu không fallback sang translator hiện tại
                                extractor = gemini_extractor if (gemini_extractor and gemini_extractor.is_available()) else translator
                                
                                ws_log_callback(f"[->] Đang quét và trích xuất từ mới bằng {extractor.__class__.__name__}...")
                                new_terms = extractor.extract_glossary_from_text(text_content, translator.glossary)
                                if new_terms:
                                    # Lưu vào cả story và global glossary
                                    added_story = glossary_mgr.save_story_glossary(new_terms)
                                    added_global = glossary_mgr.save_global_glossary(new_terms)
                                    if added_story > 0 or added_global > 0:
                                        updated_glossary = glossary_mgr.get_combined_glossary()
                                        translator.set_glossary(updated_glossary)
                                        ws_log_callback(
                                            f"[✓] Tự động trích xuất và thêm từ mới: {new_terms} "
                                            f"(Thêm vào global: {added_global}, story: {added_story})"
                                        )
                                    else:
                                        ws_log_callback(f"[i] Các từ trích xuất đã tồn tại trong glossary: {new_terms}")
                                else:
                                    ws_log_callback("[i] Không phát hiện thêm từ mới nào đáng chú ý.")
                        except Exception as e:
                            ws_log_callback(f"[WARN] Bỏ qua lỗi tự động trích xuất glossary: {e}")

                    # 2. Thực hiện dịch file
                    translator.translate_file(file_path, output_path, progress_callback=ws_log_callback)
                    
                    report = getattr(translator, "last_report", {})
                    failed_chunks = report.get("failed_chunks", [])
                    failed_p = len(failed_chunks)
                    total_p = report.get("total_paras", 0)
                    success_fallback = report.get("success_fallback", 0)
                    success_p = max(0, total_p - failed_p)
                    
                    return success_p, failed_p, total_p, success_fallback

                success_p, failed_p, total_p, success_fallback = await asyncio.to_thread(run_translation_file)
                
                input_base = os.path.splitext(os.path.basename(file_path))[0]
                report_path = os.path.join(output_dir, f"{input_base}.translation_report.json")
                report_base = f"{input_base}.translation_report.json"
                
                if failed_p > 0 or success_fallback > 0:
                    message = (
                        f"[WARN] Bản dịch được lưu tại: {output_path}\n"
                        f"[WARN] Kết quả: Thành công {success_p}/{total_p} đoạn. Có {failed_p} đoạn lỗi, {success_fallback} đoạn fallback.\n"
                        f"[WARN] File báo cáo chi tiết: {report_base}\n"
                        f"[WARN] Đường dẫn: {report_path}"
                    )
                else:
                    message = (
                        f"[✓] Bản dịch đã được lưu tại: {output_path}\n"
                        f"[✓] Kết quả: Thành công {success_p}/{total_p} đoạn (100% thành công)."
                    )
                
                await websocket.send_json({
                    "event": "file_success",
                    "index": idx,
                    "file_name": translated_file_name,
                    "output_path": output_path,
                    "success_paras": success_p,
                    "failed_paras": failed_p,
                    "total_paras": total_p,
                    "message": message
                })
                
                # Chặn chuyển chương nếu có đoạn lỗi
                # if failed_p > 0:
                #     raise ValueError(f"Chương này có {failed_p} đoạn dịch lỗi chưa được khắc phục. Tiến trình dịch bị chặn.")
            except Exception as e:
                await websocket.send_json({
                    "event": "file_error",
                    "index": idx,
                    "file_name": file_name,
                    "message": f"[✗] Lỗi khi dịch: {str(e)}"
                })
                break


        listen_task.cancel()

        if stopped:
            await websocket.send_json({
                "event": "stopped",
                "message": "[i] Quá trình dịch đã bị dừng bởi người dùng."
            })
        else:
            await websocket.send_json({
                "event": "completed",
                "message": "[✓] Đã hoàn thành dịch toàn bộ danh sách file."
            })

    except WebSocketDisconnect:
        stopped = True
    except Exception as e:
        try:
            await websocket.send_json({
                "event": "error",
                "message": f"[✗] Lỗi hệ thống dịch: {str(e)}"
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

# Hàm tự động mở trình duyệt sau khi server khởi chạy
def open_browser():
    try:
        webbrowser.open("http://localhost:8000")
    except Exception as e:
        print(f"[!] Không thể tự động mở trình duyệt: {e}")

if __name__ == "__main__":
    # Đặt thời gian trễ 1.5s trước khi mở trình duyệt để đảm bảo server đã chạy
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    import threading
    threading.Timer(1.5, open_browser).start()
    
    print("[*] Đang khởi chạy Web UI tại http://localhost:8000...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, log_level="info")
