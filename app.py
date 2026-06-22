import os
import sys
import asyncio
import webbrowser
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# Thêm thư mục hiện tại vào sys.path để python nhận diện core và sources
sys.path.insert(0, ".")

from sources.registry import SOURCES
from core.config_manager import load_config, save_config, get_default_config

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

# Hàm tự động mở trình duyệt sau khi server khởi chạy
def open_browser():
    try:
        webbrowser.open("http://localhost:8000")
    except Exception as e:
        print(f"[!] Không thể tự động mở trình duyệt: {e}")

if __name__ == "__main__":
    # Đặt thời gian trễ 1s trước khi mở trình duyệt để đảm bảo server đã chạy
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    import threading
    threading.Timer(1.5, open_browser).start()
    
    print("[*] Đang khởi chạy Web UI tại http://localhost:8000...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, log_level="info")
