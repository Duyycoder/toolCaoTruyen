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
    from translator import OLLAMA_MODELS
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
        story_id = int(config.get("story_id"))
        start_chapter_id = int(config.get("start_chapter_id"))
        num_chapters = int(config.get("num_chapters"))
        output_dir = config.get("output_dir")
        source = config.get("source")

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
        leak_threshold = int(config.get("leak_threshold_percent", 10))
        
        # Thu thập danh sách file dịch
        files_to_translate = []
        if file_paths:
            files_to_translate = [os.path.abspath(f) for f in file_paths]
        elif folder_path:
            folder_abs = os.path.abspath(folder_path)
            if os.path.exists(folder_abs) and os.path.isdir(folder_abs):
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

        # Khởi tạo Engine tương ứng
        from translator import TRANSLATOR_ENGINES, OLLAMA_MODELS
        
        if engine_type == "ollama":
            chunk_size = OLLAMA_MODELS.get(ollama_model, {}).get("chunk_size_chars", 350)
            translator = TRANSLATOR_ENGINES["ollama"](
                model=ollama_model,
                max_chunk_chars=chunk_size,
                leak_threshold_percent=leak_threshold
            )
        elif engine_type == "gemini":
            translator = TRANSLATOR_ENGINES["gemini"](
                api_key=gemini_api_key,
                model=gemini_model,
                leak_threshold_percent=leak_threshold
            )
        else:
            await websocket.send_json({
                "event": "error",
                "message": f"[✗] Nguồn dịch '{engine_type}' không hợp lệ."
            })
            return

        # Chạy task lắng nghe dừng song song
        listen_task = asyncio.create_task(listen_for_client_messages())

        # Vòng lặp xử lý từng file
        for idx, file_path in enumerate(files_to_translate, 1):
            if stopped:
                break
                
            file_name = os.path.basename(file_path)
            await websocket.send_json({
                "event": "file_start",
                "index": idx,
                "file_name": file_name,
                "message": f"\n[***] Bắt đầu dịch file {idx}/{len(files_to_translate)}: {file_name}"
            })

            file_dir = os.path.dirname(file_path)
            output_dir = os.path.join(file_dir, "dich")
            output_path = os.path.join(output_dir, file_name)

            try:
                def run_translation_file():
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read()
                    
                    translated = translator.translate(text, progress_callback=ws_log_callback)
                    
                    os.makedirs(output_dir, exist_ok=True)
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(translated)
                    
                    # Trích xuất thống kê
                    total_p = len([p for p in re.split(r"\n\n", text) if p.strip()])
                    failed_p = len(re.findall(r"> ⚠️ \[Đoạn này AI dịch không thành công", translated))
                    success_p = max(0, total_p - failed_p)
                    return success_p, failed_p, total_p

                success_p, failed_p, total_p = await asyncio.to_thread(run_translation_file)
                
                await websocket.send_json({
                    "event": "file_success",
                    "index": idx,
                    "file_name": file_name,
                    "output_path": output_path,
                    "success_paras": success_p,
                    "failed_paras": failed_p,
                    "total_paras": total_p,
                    "message": f"[✓] Bản dịch đã được lưu tại: {output_path}\n"
                               f"[✓] Kết quả: Thành công {success_p}/{total_p} đoạn, {failed_p} đoạn cần xem lại thủ công."
                })
            except Exception as e:
                await websocket.send_json({
                    "event": "file_error",
                    "index": idx,
                    "file_name": file_name,
                    "message": f"[✗] Lỗi khi dịch: {str(e)}"
                })

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
