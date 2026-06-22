import os
import sys
import asyncio
import webbrowser
import json
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Thêm thư mục hiện tại vào sys.path để python nhận diện core và sources
sys.path.insert(0, ".")

from sources.registry import SOURCES, get_source
from core.config_manager import load_config, save_config, get_default_config
from core.crawler_engine import download_chapters

app = FastAPI(title="Tool Cào Truyện Web UI")

class ConfigModel(BaseModel):
    base_url: str
    output_dir: str
    source: str

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

# API 3: Lưu cấu hình mới
@app.post("/api/config")
async def update_config(config: ConfigModel):
    try:
        save_config(config.base_url, config.output_dir, config.source)
        return {"status": "success", "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi lưu cấu hình: {str(e)}")

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
