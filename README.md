# 📖 Tool Cào Truyện Chữ Tự Động & Dịch Thuật AI (Bypass Cloudflare)

Công cụ chạy trên máy cá nhân giúp tự động tải truyện chữ từ website **69shuba.com** (và các trang tương tự), vượt qua lớp bảo vệ chống bot, làm sạch nội dung rác và hỗ trợ dịch thuật thông qua AI Local. Hỗ trợ cả giao diện Terminal (CLI) lẫn giao diện đồ họa Web (Web UI).

---

## 🌟 Tính năng nổi bật
* **Bypass Cloudflare tự động:** Sử dụng Selenium để vượt qua lớp bảo vệ Cloudflare Managed Challenge ("Just a moment...") bằng trình duyệt ẩn danh thật.
* **Đầu ra sạch sẽ:** Tự động loại bỏ toàn bộ quảng cáo, text rác, liên kết website ẩn trong nội dung chương truyện.
* **Dịch thuật AI Local:** Tích hợp Ollama dịch chương trực tiếp từ tiếng Trung sang tiếng Việt mượt mà, văn phong tự nhiên.
* **Tự động lưu tiến độ:** Nếu đang tải mà bị mất mạng hoặc tắt tool, lần sau chạy lại tool sẽ tự động tiếp tục tải từ chương bị gián đoạn, tránh tải trùng lặp.
* **Giao diện đa dạng:**
  * **Web UI (FastAPI & WebSocket):** Giao diện Web hiện đại, chọn thư mục lưu qua Windows Dialog, theo dõi tiến độ thời gian thực (real-time) và hỗ trợ nút Dừng giữa chừng.
  * **CLI Terminal:** Thao tác nhanh gọn bằng dòng lệnh truyền thống.
* **Cài đặt 1-Click:** File cài đặt tự động `setup.bat` làm mọi thứ từ thư viện Python đến tải mô hình AI.

---

## ⚙️ Yêu cầu phần cứng & Hệ thống (Prerequisites)

* **Hệ điều hành:** Windows 10/11.
* **Google Chrome:** Bắt buộc phải cài đặt trình duyệt Chrome bản mới nhất trên máy (để Selenium điều khiển vượt Cloudflare). Tải tại: [https://www.google.com/chrome/](https://www.google.com/chrome/).
* **Python 3.x:** Tải tại [https://www.python.org/downloads/](https://www.python.org/downloads/).
  > [!IMPORTANT]
  > Khi cài đặt Python trên Windows, bạn **bắt buộc** phải tích chọn ô **"Add Python to PATH"** (hoặc **"Add python.exe to PATH"**) ở giao diện cài đặt đầu tiên.
* **Cấu hình phần cứng tối thiểu cho tính năng Dịch AI:**
  * Card màn hình: **GPU NVIDIA** có hỗ trợ driver CUDA mới nhất.
  * Dung lượng bộ nhớ đồ họa (VRAM): **Tối thiểu 6GB VRAM** để chạy mô hình dịch `qwen2.5:7b-instruct` (Khuyến nghị **8GB VRAM trở lên** để dịch mượt mà hoặc nâng cấp lên mô hình `14B` trong tương lai).
  * Dung lượng ổ cứng: Trống **ít nhất 5GB** cho mô hình AI.

---

## 🚀 Hướng dẫn cài đặt trên máy mới (Chỉ 3 bước)

Chúng tôi đã đóng gói toàn bộ quá trình thiết lập phức tạp vào tệp tự động hóa. Người dùng chỉ cần làm theo 3 bước sau:

1. **Tải/Clone mã nguồn này về máy** và giải nén vào một thư mục bất kỳ.
2. Nhấp đúp chuột vào file **`setup.bat`** ở thư mục gốc:
   * Script sẽ tự động kiểm tra Python, Google Chrome.
   * Tự động cài các thư viện Python cần thiết qua `requirements.txt`.
   * Tự động nhận diện Ollama, tải và cài đặt Ollama ngầm (Silent Install) nếu máy chưa có.
   * Tự động khởi chạy máy chủ Ollama và tải mô hình AI dịch thuật `qwen2.5:7b-instruct` (4.7 GB).
   * Kiểm tra và thông báo khi toàn bộ hệ thống đã sẵn sàng.
3. Chạy ứng dụng:
   * **Chạy Web UI (Khuyên dùng):** Mở CMD gõ `python app.py` (Trình duyệt sẽ tự động mở trang giao diện Web tuyệt đẹp tại địa chỉ `http://localhost:8000`).
   * **Chạy CLI (Dòng lệnh):** Nhấp đúp chuột vào file `run.bat` để chạy trên cửa sổ Terminal cũ.

---

## 💡 Hướng dẫn sử dụng giao diện Web UI

Sau khi chạy `python app.py`, trình duyệt sẽ mở giao diện Web. Bạn chỉ cần điền các thông tin:
1. **Nguồn truyện:** Chọn nguồn truyện phù hợp (mặc định: `69shuba`).
2. **ID Bộ Truyện:** Lấy từ link bộ truyện cần tải. Ví dụ: Nếu link là `https://www.69shuba.com/book/90438.htm` thì ID truyện là `90438`.
3. **ID Chương bắt đầu:** Điền số thứ tự ID chương mà bạn muốn tải (Ví dụ: `40755198`).
4. **Số lượng chương muốn tải:** Nhập số lượng chương cần tải về.
5. **Thư mục lưu file:** Bấm nút **"Duyệt..."** để mở hộp thoại hệ thống chọn thư mục trực quan theo ý muốn.
6. Bấm **"Bắt Đầu Tải Truyện"** để chạy. Bạn có thể theo dõi tiến độ chạy real-time trên thanh tiến trình và bảng nhật ký (Logs). Nhấn nút **"Dừng Tải Truyện"** (Màu đỏ) bất kỳ lúc nào để hủy tác vụ an toàn.

---

## ❓ Các câu hỏi thường gặp (Q&A)

### 1. File setup.bat chạy lại nhiều lần có tải lại mô hình AI không?
* Không. Script `setup.bat` được thiết kế có tính **Idempotent (Không trùng lặp)**. Nếu hệ thống quét thấy Ollama và model `qwen2.5:7b-instruct` đã được tải thành công từ trước, nó sẽ lập tức báo "Đã sẵn sàng" và bỏ qua, không tải lại gì cả.

### 2. Có thể đổi mô hình dịch hoặc cấu hình nâng cao ở đâu?
* Toàn bộ cấu hình phiên chạy được đồng bộ tự động xuống file `config.json`. Mọi thông số về model, link cào và thư mục mặc định người dùng đều có thể tinh chỉnh trực tiếp qua giao diện Web UI, hệ thống sẽ tự động lưu lại cho phiên làm việc sau.
