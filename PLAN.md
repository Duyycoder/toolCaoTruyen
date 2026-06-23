# Kế Hoạch Refactor & Tài Liệu Khảo Sát - Phase 0

Tài liệu này ghi lại thông tin phân tích tĩnh của file `main.py` hiện tại, mô tả kiến trúc gọi hàm hiện tại, và đánh giá các rủi ro khi tiến hành refactor theo Strategy Pattern.

---

## 1. Khảo Sát Mã Nguồn Hiện Tại (`main.py`)

### 1.1. Các Hằng Số Toàn Cục (Global Constants)
* **`DEFAULT_BASE_URL` (str):** `"https://www.69shuba.com/txt"` — URL gốc mặc định của website truyện.
* **`DEFAULT_OUTPUT_DIR` (str):** `"./truyen_tai_ve"` — Thư mục mặc định để lưu trữ truyện tải về.
* **`CONFIG_FILE` (str):** `"config.json"` — Tên file cấu hình JSON lưu trạng thái phiên chạy trước.
* **`MAX_CONSECUTIVE_FAILURES` (int):** `10` — Số lần lỗi tải liên tiếp cho phép trước khi kích hoạt Circuit Breaker dừng tải.
* **`AD_PATTERNS` (list[str]):** Mảng chứa các regex patterns đại diện cho các dòng text quảng cáo cần lọc bỏ khỏi nội dung truyện.

### 1.2. Các Lớp Hiện Tại (Classes)
* **`Color`**:
  * **Docstring:** `"""Mã màu ANSI cho output terminal."""`
  * **Các thuộc tính:**
    * `RESET = "\033[0m"`
    * `RED = "\033[91m"`
    * `GREEN = "\033[92m"`
    * `YELLOW = "\033[93m"`
    * `BLUE = "\033[94m"`
    * `MAGENTA = "\033[95m"`
    * `CYAN = "\033[96m"`
    * `BOLD = "\033[1m"`
    * `DIM = "\033[2m"`

### 1.3. Các Hàm Hiện Tại (Functions)

#### 1. `load_config() -> Optional[Dict[str, str]]`
* **Docstring:** `Đọc file config.json (nếu tồn tại) để lấy cấu hình lần chạy trước.`
* **Trả về:** `Dict` chứa cấu hình đã lưu hoặc `None` nếu file không tồn tại hoặc lỗi định dạng.

#### 2. `save_config(base_url: str, output_dir: str) -> None`
* **Docstring:** `Lưu cấu hình Base URL và Thư mục lưu file vào config.json để tái sử dụng ở lần chạy sau.`
* **Tham số:**
  * `base_url`: URL gốc của website truyện.
  * `output_dir`: Đường dẫn thư mục lưu file.

#### 3. `get_user_input() -> Tuple[str, int, int, int, str]`
* **Docstring:** `Hỏi người dùng nhập các thông tin cấu hình qua terminal. Nếu người dùng bấm Enter bỏ trống, sẽ dùng giá trị mặc định. Nếu có config từ lần trước, hỏi người dùng có muốn tái sử dụng không.`
* **Trả về:** Tuple gồm `(base_url, story_id, start_chapter_id, num_chapters, output_dir)`.

#### 4. `create_browser() -> webdriver.Chrome`
* **Docstring:** `Khởi tạo Chrome browser với cấu hình chống phát hiện automation. Cửa sổ được đẩy ra ngoài màn hình để không ảnh hưởng người dùng.`
* **Trả về:** Instance `webdriver.Chrome` đã cấu hình chống bot và sẵn sàng sử dụng.

#### 5. `get_html(driver: webdriver.Chrome, url: str, is_first_request: bool = False) -> Optional[str]`
* **Docstring:** `Dùng Chrome browser để tải HTML của URL. Tự động chờ Cloudflare challenge nếu gặp.`
* **Tham số:**
  * `driver`: Instance Chrome driver đang chạy.
  * `url`: URL trang truyện cần tải.
  * `is_first_request`: Có phải yêu cầu đầu tiên hay không (quyết định thời gian chờ CF lâu hơn).
* **Trả về:** Mã HTML nguồn dạng chuỗi hoặc `None` nếu thất bại.

#### 6. `parse_chapter(html: str) -> Optional[Tuple[str, str, str]]`
* **Docstring:** `Phân tích HTML để trích xuất tên truyện, tên chương và nội dung. Sử dụng BeautifulSoup4 với các CSS Selector phù hợp cho 69shuba.com.`
* **Tham số:**
  * `html`: Chuỗi mã nguồn HTML.
* **Trả về:** Tuple chứa `(tên_truyện, tên_chương, nội_dung)` hoặc `None` nếu không hợp lệ.

#### 7. `_clean_content(content_div: BeautifulSoup) -> str`
* **Docstring:** `Làm sạch nội dung HTML: loại bỏ quảng cáo, chuyển đổi thẻ HTML thành format Markdown phù hợp.`
* **Tham số:**
  * `content_div`: Thẻ BeautifulSoup đại diện khối nội dung chính cần làm sạch.
* **Trả về:** Chuỗi văn bản đã làm sạch sẵn sàng lưu vào file.

#### 8. `sanitize_filename(name: str) -> str`
* **Docstring:** `Dọn dẹp tên file/folder: loại bỏ ký tự không hợp lệ trên Windows/Linux (\ / : * ? " < > |).`
* **Tham số:**
  * `name`: Chuỗi ký tự thô.
* **Trả về:** Tên file hợp lệ đã được làm sạch.

#### 9. `save_to_markdown(output_dir: str, story_name: str, chapter_name: str, content: str, chapter_index: int) -> str`
* **Docstring:** `Lưu nội dung chương thành file Markdown (.md).`
* **Tham số:**
  * `output_dir`: Thư mục gốc lưu trữ.
  * `story_name`: Tên truyện (dùng làm tên thư mục con).
  * `chapter_name`: Tên chương (dùng làm tên file).
  * `content`: Nội dung truyện đã làm sạch.
  * `chapter_index`: Số thứ tự để đánh chỉ mục file.
* **Trả về:** Đường dẫn file `.md` đã lưu thành công.

#### 10. `download_chapters(base_url: str, story_id: int, start_chapter_id: int, num_chapters: int, output_dir: str) -> None`
* **Docstring:** `Vòng lặp chính: tải từng chương, parse, và lưu file. Tự động xử lý ID gap và có cơ chế circuit breaker.`
* **Tham số:** Các thông số cấu hình do người dùng chọn hoặc lấy từ config.

#### 11. `main() -> None`
* **Docstring:** `Điểm khởi chạy chương trình.`

---

## 2. Sơ Đồ Kiến Trúc Hiện Tại (Kiểu Text)

Hiện tại toàn bộ logic nằm trong một file duy nhất `main.py` chạy dạng tuần tự (Procedural Scripting).
Sơ đồ phân cấp gọi hàm như sau:

```text
main.py (Entrypoint)
  └── main()
        ├── get_user_input()
        │     ├── load_config()
        │     └── save_config()
        │
        └── download_chapters()
              ├── create_browser() -> Trả về driver Selenium
              │
              └── Vòng lặp tải chương:
                    ├── get_html(driver, url) -> Tải HTML (bypass Cloudflare)
                    │
                    ├── parse_chapter(html) -> Bóc tách dữ liệu
                    │     └── _clean_content(content_div) -> Lọc ad & chuẩn hóa văn bản
                    │
                    └── save_to_markdown(...) -> Ghi file ra ổ cứng
                          └── sanitize_filename(name) -> Lọc ký tự cấm của OS
```

---

## 3. Đánh Giá Rủi Ro Khi Refactor

Khi chuyển đổi kiến trúc sang **Strategy Pattern** (để hỗ trợ cào từ nhiều site khác nhau), các rủi ro sau cần được kiểm soát chặt chẽ:

1. **Rủi ro vỡ hoạt động của file script khởi chạy (.bat):**
   * *Mô tả:* Hai file `run.bat` và `install.bat` đang gọi trực tiếp `python main.py`. Nếu quá trình refactor thay đổi tên file chính hoặc chia cấu trúc thư mục thành gói (packages) mà không cập nhật lại các file bat này, người dùng sẽ gặp lỗi không tìm thấy module hoặc file chạy.
   * *Giải pháp:* Luôn giữ `main.py` ở thư mục root làm entrypoint chính và chỉ import các module con vào đó.

2. **Tương thích ngược cấu hình (`config.json`):**
   * *Mô tả:* Người dùng hiện tại có file `config.json` chứa cấu hình cũ (`base_url` và `output_dir`). Nếu Strategy Pattern yêu cầu thay đổi cấu trúc của file này (ví dụ thêm loại site truyện `"site_type": "69shuba"`), code đọc config cũ phải có cơ chế fallback tự động điền các giá trị mặc định để tránh quăng lỗi `KeyError`.

3. **Quản lý vòng đời Driver Selenium (Trình duyệt):**
   * *Mô tả:* Mỗi site (Strategy) có thể có cơ chế chống bot khác nhau. Nếu đặt logic khởi tạo và tắt WebDriver vào bên trong từng lớp Strategy, việc chuyển đổi qua lại hoặc tải tuần tự sẽ cực kỳ chậm vì phải mở/đóng Chrome liên tục.
   * *Giải pháp:* Tách biệt lớp điều phối phiên tải (Engine) giữ driver và truyền driver này vào hàm `scrape` của Strategy, đảm bảo Chrome chỉ khởi tạo một lần duy nhất suốt phiên chạy.

4. **Biến dạng tên file Markdown làm mất liên kết chương cũ:**
   * *Mô tả:* Hàm `sanitize_filename` hiện tại quyết định cách đặt tên thư mục và tên file truyện. Nếu refactor làm thay đổi giải thuật làm sạch tên (ví dụ thay thế ký tự khác đi), lần chạy sau tool sẽ lưu vào một thư mục mới hoàn toàn hoặc tạo file trùng lặp thay vì ghi đè lên file cũ đã tải.
   * *Giải pháp:* Giữ nguyên logic của `sanitize_filename` và `save_to_markdown` dưới dạng utility dùng chung cho toàn bộ dự án, tránh viết lại logic này trong các Strategy riêng lẻ.

5. **Sai lệch Regex Lọc Quảng Cáo:**
   * *Mô tả:* Quảng cáo của mỗi website có đặc trưng riêng. Nếu gộp chung `AD_PATTERNS` hoặc chia nhỏ sai cách, nội dung truyện của trang này có thể bị lọc mất chữ có nghĩa hoặc trang kia không được làm sạch quảng cáo.
   * *Giải pháp:* Tách biệt danh sách ad patterns của từng website vào các lớp Strategy tương ứng thay vì dùng chung một mảng toàn cục.
