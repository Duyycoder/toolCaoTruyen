# 📖 Tool Cào Truyện Chữ Tự Động (Bypass Cloudflare)

Công cụ chạy trên Terminal giúp tự động tải truyện chữ từ website **69shuba.com** (và các trang tương tự), xử lý nội dung sạch sẽ và lưu dưới dạng các file **Markdown (.md)** để đọc offline hoặc chuyển đổi sang EPUB/MOBI.

---

## 🌟 Tính năng nổi bật
* **Bypass Cloudflare tự động:** Sử dụng Selenium để vượt qua lớp bảo vệ Cloudflare Managed Challenge ("Just a moment...") một cách mượt mà.
* **Đầu ra sạch sẽ:** Tự động loại bỏ toàn bộ quảng cáo, text rác, liên kết website ẩn trong nội dung chương truyện.
* **Tự động lưu tiến độ:** Nếu đang tải mà bị mất mạng hoặc tắt tool, lần sau chạy lại tool sẽ tự động tiếp tục tải từ chương bị gián đoạn, tránh tải trùng lặp.
* **Định dạng chuẩn:** Lưu file dưới định dạng Markdown UTF-8 tiếng Trung hoặc tiếng Việt đầy đủ, tiêu đề rõ ràng, cấu trúc thư mục phân loại theo Tên Truyện.
* **Thân thiện với người mới:** Hỗ trợ file chạy tự động một-click (`run.bat`), tự động cài đặt mọi thứ cần thiết.

---

## ⚙️ Điều kiện sử dụng & Những điều cần biết

### 1. Yêu cầu hệ thống (Prerequisites)
Để chạy được công cụ này, máy tính của bạn cần có:
1. **Hệ điều hành:** Windows (hoặc macOS/Linux nếu chạy thủ công qua Terminal).
2. **Google Chrome:** Bắt buộc phải cài đặt trình duyệt Chrome bản mới nhất trên máy (vì tool sẽ dùng Chrome thực tế để vượt qua Cloudflare). Tải Chrome tại: [https://www.google.com/chrome/](https://www.google.com/chrome/).
3. **Python 3.x:** Tải bản mới nhất tại [https://www.python.org/downloads/](https://www.python.org/downloads/).
   > [!IMPORTANT]
   > Khi cài đặt Python trên Windows, bạn **bắt buộc** phải tích chọn ô **"Add Python to PATH"** (hoặc **"Add python.exe to PATH"**) ở giao diện cài đặt đầu tiên. Nếu không tích chọn ô này, máy tính sẽ không nhận diện được lệnh chạy Python.

### 2. Kiến thức về Web Truyện & Cơ chế hoạt động
* **Cơ chế chống cào dữ liệu (Anti-Scraping):** Các trang web truyện chữ lớn như `69shuba.com` sử dụng dịch vụ của Cloudflare để chống DDOS và chống bot cào dữ liệu. Khi truy cập bằng các thư viện lập trình thông thường (như `requests` hay `urllib` trong Python), hệ thống sẽ trả về lỗi **HTTP 403 Forbidden** vì phát hiện đó là bot.
* **Giải pháp của công cụ:** Tool sử dụng thư viện **Selenium** để mở một cửa sổ Chrome ẩn danh. Trình duyệt này sẽ thực thi JavaScript, gửi các thông số vân tay trình duyệt giống y như người dùng thật đang đọc truyện. Vì vậy, Cloudflare sẽ cho phép truy cập mà không chặn lại.
* **Trải nghiệm người dùng:** Khi chạy tool, bạn sẽ thấy một cửa sổ trình duyệt Chrome nhỏ tự động mở lên và được đẩy xuống góc màn hình để không làm phiền bạn. Đừng tắt cửa sổ này đi, tool đang sử dụng nó để tải truyện. Nó sẽ tự động đóng khi tải xong.

---

## 🚀 Hướng dẫn cài đặt & Sử dụng (Dành cho người mới)

Chúng tôi đã thiết kế các file chạy tự động để bạn không cần gõ bất kỳ dòng lệnh nào trong Command Prompt.

### Cách chạy nhanh nhất (Khuyên dùng)
1. **Tải mã nguồn này về máy** và giải nén vào một thư mục bất kỳ.
2. Đảm bảo máy tính đã cài đặt **Google Chrome** và **Python** (đã tích Add to PATH).
3. Nhấp đúp chuột vào file **`run.bat`**:
   * Tool sẽ tự động kiểm tra xem máy bạn đã cài thư viện chưa.
   * Nếu chưa cài, nó sẽ **tự động cài đặt** các thư viện cần thiết (`selenium`, `beautifulsoup4`) thông qua file `requirements.txt`.
   * Khởi chạy chương trình và hiển thị giao diện Terminal màu sắc trực quan để bạn bắt đầu nhập thông tin tải truyện.

---

## 💡 Hướng dẫn sử dụng chi tiết trên giao diện Terminal

Khi công cụ khởi chạy, màn hình sẽ yêu cầu bạn nhập các thông tin sau:
1. **Nhập link gốc truyện (Base URL):** Nhấn `Enter` để chọn mặc định (`https://www.69shuba.com/txt`) hoặc nhập link khác nếu có.
2. **Nhập ID truyện:** Là dãy số nằm trên đường dẫn của bộ truyện bạn muốn tải.
   * *Ví dụ:* Nếu link truyện là `https://www.69shuba.com/book/90438.htm` thì ID truyện là **`90438`**.
3. **ID Chương bắt đầu:** Điền số thứ tự ID chương mà bạn muốn tải (Ví dụ: `1` hoặc `10`). Nhấn `Enter` để mặc định tải từ chương 1.
4. **Số lượng chương muốn tải:** Nhập số lượng chương bạn muốn tải (Ví dụ: `50` chương). Nhấn `Enter` để tải toàn bộ các chương còn lại cho đến chương mới nhất.
5. **Khoảng cách thời gian nghỉ (giây):** Thời gian giãn cách giữa mỗi lần tải chương để tránh bị máy chủ phát hiện và chặn IP. Nên để mặc định từ `1` đến `3` giây.

Truyện tải về sẽ được lưu trữ tự động trong thư mục `truyen_tai_ve/<Tên_Truyện>/` dưới dạng từng file `.md`.

---

## ❓ Các câu hỏi thường gặp (Q&A)

### 1. Tại sao không thể tạo một file `.env` chạy luôn mà không cần cài thư viện?
* **Bản chất của Python:** Python là một ngôn ngữ lập trình dạng thông dịch (Scripting). Các đoạn mã cần các thư viện bổ sung như `selenium` (để điều khiển Chrome) và `beautifulsoup4` (để xử lý nội dung trang web). Những thư viện này không được tích hợp sẵn trong Python mặc định của hệ thống.
* **File `.env` là gì?** File `.env` chỉ dùng để lưu trữ các thông tin cấu hình môi trường (như mật khẩu, khóa API, cổng chạy local,...), nó **không có khả năng đóng gói thư viện**.
* **Giải pháp tiện lợi nhất:** Thay vì bắt bạn tự gõ các lệnh cài đặt phức tạp, file `run.bat` đã đóng vai trò tự động tải và cài các thư viện này ngay trong lần đầu tiên chạy. Người dùng chỉ cần nhấp đúp file là dùng được ngay, tiện lợi tương tự như file cài đặt thông thường.

### 2. Có bị rò rỉ thông tin cá nhân khi chạy trình duyệt Chrome không?
* Không. Trình duyệt Chrome được mở qua Selenium chạy ở chế độ cấu hình sạch (Clean Profile) hoặc ẩn danh tạm thời, không sử dụng cookie hay tài khoản Google cá nhân của bạn, đảm bảo an toàn tuyệt đối.

### 3. File cấu hình `config.json` dùng để làm gì?
File này dùng để bạn lưu cấu hình mặc định:
```json
{
  "base_url": "https://www.69shuba.com/txt",
  "output_dir": "./truyen_tai_ve"
}
```
Bạn có thể mở file này bằng Notepad để sửa thư mục lưu truyện (`output_dir`) hoặc link gốc truyện mặc định nếu muốn.
