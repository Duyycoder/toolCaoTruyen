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

Sau khi chạy `python app.py`, trình duyệt sẽ mở giao diện Web với hai tab chức năng độc lập:

### 1. Tab Cào Truyện Web
Tải nội dung thô tiếng Trung từ website về máy:
1. **Nguồn truyện:** Chọn nguồn truyện phù hợp (mặc định: `69shuba`).
2. **ID Bộ Truyện:** Lấy từ link bộ truyện cần tải. Ví dụ: Nếu link là `https://www.69shuba.com/book/90438.htm` thì ID truyện là `90438`.
3. **ID Chương bắt đầu:** Điền số thứ tự ID chương mà bạn muốn tải (Ví dụ: `40755198`).
4. **Số lượng chương muốn tải:** Nhập số lượng chương cần tải về.
5. **Thư mục lưu file:** Bấm nút **"Duyệt..."** để chọn thư mục lưu qua Windows Dialog trực quan.
6. Bấm **"Bắt Đầu Tải Truyện"** để chạy. Nhấn nút **"Dừng Tải Truyện"** (Màu đỏ) bất kỳ lúc nào để dừng.

### 2. Tab Dịch Truyện Offline
Dịch các file `.md` tiếng Trung sang tiếng Việt mượt mà với nhiều lựa chọn Engine và Model:
1. **Chọn đối tượng dịch:** 
   - Bấm **"Chọn File..."** để chọn một hoặc nhiều file `.md` cụ thể trên ổ đĩa.
   - Hoặc bấm **"Chọn Thư Mục..."** để quét và dịch toàn bộ file `.md` trong thư mục đó.
2. **Engine dịch thuật:**
   - **Ollama (Chạy Offline Local):** Dùng model AI chạy cục bộ không cần internet. Bạn có thể chọn giữa:
     - *Qwen2.5 7B (Đã kiểm thử):* Model khuyên dùng, hoạt động mượt mà với card đồ họa 6-8GB VRAM. Đã được đo đạc tối ưu với chunk size 350 ký tự (tỉ lệ rò rỉ chữ Trung trung bình chỉ ~0.40%).
     - *Qwen3 8B (Mới, chưa tối ưu riêng):* Model thử nghiệm, sử dụng tạm cấu hình chunk size giống bản 7B. Bạn cần chạy lệnh `ollama pull qwen3:8b` thủ công để tải model trước khi dùng.
   - **Gemini API:** Dịch trực tuyến bằng Gemini API của Google (cần điền **Gemini API Key** và kết nối internet). Rất nhanh và dịch trơn tru bằng model `gemini-2.5-flash`.
3. **Cơ chế 2 Tầng chống rò rỉ chữ Trung (Anti-leakage):**
   - *Tầng 1 (Per-chunk Retry):* Tách văn bản thành các đoạn nhỏ (350 ký tự cho Ollama), nếu kết quả dịch chunk vượt quá ngưỡng rò rỉ (mặc định 10%), model tự hạ nhiệt độ và dịch lại.
   - *Tầng 2 (Paragraph Repair):* Ghép lại toàn bộ file và quét từng đoạn văn nhỏ. Vá cục bộ những câu bị rò rỉ chữ Hán ở ranh giới chunk.
   - *Đánh dấu lỗi thủ công:* Nếu đoạn văn vẫn dịch lỗi sau cả 2 tầng, hệ thống sẽ đánh dấu rõ ràng dạng `> ⚠️ [Đoạn này AI dịch không thành công, giữ nguyên bản gốc]\n\n[Nội dung gốc]` thay vì để trôi qua âm thầm. Đây là **thiết kế có chủ đích** của hệ thống vì các model 6-8B local không đảm bảo dịch hoàn hảo 100% văn tự sự novel dài.

---

## ❓ Các câu hỏi thường gặp (Q&A)

### 1. File setup.bat chạy lại nhiều lần có tải lại mô hình AI không?
* Không. Script `setup.bat` được thiết kế có tính **Idempotent (Không trùng lặp)**. Nếu hệ thống quét thấy Ollama và model `qwen2.5:7b-instruct` đã được tải thành công từ trước, nó sẽ lập tức báo "Đã sẵn sàng" và bỏ qua, không tải lại gì cả.

### 2. Làm thế nào để dùng model Qwen3-8B?
* Nhằm tiết kiệm dung lượng đĩa cho người dùng, `setup.bat` không tự động tải mô hình này. Nếu muốn thử nghiệm, vui lòng chạy lệnh dưới đây trong cửa sổ CMD của bạn:
  ```bash
  ollama pull qwen3:8b
  ```
  Sau khi tải xong, quay lại giao diện Web UI, dropdown chọn model sẽ tự động cập nhật trạng thái sang "Model đã sẵn sàng".

### 3. Cách lấy Gemini API Key miễn phí?
* Bạn có thể truy cập [Google AI Studio](https://aistudio.google.com/), đăng nhập bằng tài khoản Google cá nhân và nhấn "Create API Key" để nhận Key miễn phí dùng cho dịch thuật trực tuyến tốc độ cao.

