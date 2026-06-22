import sys
from sources.shuba69 import Shuba69Parser

def run_tests():
    print("==================================================")
    print("   CHẠY KIỂM THỬ THỦ CÔNG: PHASE 1 REFACTOR")
    print("==================================================")

    # ----------------------------------------------------
    # MOCK HTML 1: Trường hợp chuẩn (Có biến bookinfo JS)
    # ----------------------------------------------------
    mock_html_standard = """
    <html>
    <head>
        <title>Đại Lập Thành Tiên-Chương 1: Bắt Đầu Hành Trình-69书吧</title>
        <script>
            var bookinfo = {
                articlename: 'Đại Lập Thành Tiên',
                chaptername: 'Chương 1: Bắt Đầu Hành Trình',
                next_page: '90438/40755199',
                preview_page: '90438'
            };
        </script>
    </head>
    <body>
        <div class="txtnav">
            <h1 class="hide720">Chương 1: Bắt Đầu Hành Trình</h1>
            <div class="txtinfo">Ngày cập nhật: 2026-06-22</div>
            
            Đây là nội dung chương truyện thứ nhất dùng để kiểm tra.<br/>
            Dòng này chứa quảng cáo 69shuba.com cần phải bị lọc bỏ.
            <p>Đoạn văn thứ nhất trong thẻ p.</p>
            Dòng này hoàn toàn sạch sẽ và bình thường.
            
            <div class="txtbottom">
                <a href="#">Chương sau</a>
            </div>
        </div>
    </body>
    </html>
    """

    # ----------------------------------------------------
    # MOCK HTML 2: Trường hợp fallback (Không có biến bookinfo)
    # ----------------------------------------------------
    mock_html_fallback = """
    <html>
    <head>
        <title>Vũ Động Càn Khôn - Chương 2: Thử Nghiệm Fallback - 69书吧</title>
    </head>
    <body>
        <div class="bread">
            <a href="/">首页</a> > <a href="/sort/1.htm">Huyền Huyễn</a> > <a href="/book/123.htm">Vũ Động Càn Khôn</a>
        </div>
        <div id="txtright">
            <h1>Chương 2: Thử Nghiệm Fallback</h1>
            <script>Một script rác cần xóa</script>
            Nội dung dòng 1 dài hơn để vượt qua kiểm tra độ dài tối thiểu 50 ký tự của parser.
            Nội dung dòng 2 chứa 69书吧 quảng cáo cần xóa hoàn toàn ra khỏi bài viết.
            Nội dung dòng 3 cũng cần dài hơn một chút để đảm bảo văn bản sau khi lọc sạch vẫn đủ điều kiện hiển thị trên ứng dụng.
        </div>
    </body>
    </html>
    """

    parser = Shuba69Parser(base_url="https://www.69shuba.com/txt")

    # --- Test Case 1 ---
    print("\n[+] Test Case 1: Standard parsing (với biến bookinfo JS)")
    result1 = parser.parse_chapter(mock_html_standard)
    if result1 is None:
        print("    [✗] Thất bại: parse_chapter trả về None")
        sys.exit(1)
        
    story_name1, chapter_name1, content1 = result1
    print(f"    Tên truyện: {story_name1}")
    print(f"    Tên chương: {chapter_name1}")
    print("    Nội dung bóc tách:")
    print("    " + "\n    ".join(content1.split("\n")))

    # Kiểm thử các xác nhận (assertions)
    assert story_name1 == "Đại Lập Thành Tiên", f"Sai tên truyện: {story_name1}"
    assert chapter_name1 == "Chương 1: Bắt Đầu Hành Trình", f"Sai tên chương: {chapter_name1}"
    assert "69shuba.com" not in content1, "Chưa lọc quảng cáo 69shuba.com"
    assert "Đoạn văn thứ nhất trong thẻ p." in content1, "Mất nội dung trong thẻ p"
    assert "Ngày cập nhật" not in content1, "Chưa lọc div.txtinfo"
    assert "Chương sau" not in content1, "Chưa lọc div.txtbottom"
    print("    [✓] Đạt chuẩn (PASSED)")

    # --- Test Case 2 ---
    print("\n[+] Test Case 2: Fallback parsing (không có biến bookinfo, dùng DOM elements)")
    result2 = parser.parse_chapter(mock_html_fallback)
    if result2 is None:
        print("    [✗] Thất bại: parse_chapter trả về None ở chế độ fallback")
        sys.exit(1)
        
    story_name2, chapter_name2, content2 = result2
    print(f"    Tên truyện: {story_name2}")
    print(f"    Tên chương: {chapter_name2}")
    print("    Nội dung bóc tách:")
    print("    " + "\n    ".join(content2.split("\n")))

    assert story_name2 == "Vũ Động Càn Khôn", f"Sai tên truyện fallback: {story_name2}"
    assert chapter_name2 == "Chương 2: Thử Nghiệm Fallback", f"Sai tên chương fallback: {chapter_name2}"
    assert "69书吧" not in content2, "Chưa lọc quảng cáo 69书吧 ở fallback"
    assert "Nội dung dòng 1 dài hơn" in content2, "Mất nội dung dòng 1"
    assert "Một script rác" not in content2, "Thẻ script chưa được loại bỏ"
    print("    [✓] Đạt chuẩn (PASSED)")

    # --- Test Case 3: URL Building ---
    print("\n[+] Test Case 3: URL building")
    url = parser.build_chapter_url(90438, 40755198)
    print(f"    URL tạo ra: {url}")
    assert url == "https://www.69shuba.com/txt/90438/40755198"
    print("    [✓] Đạt chuẩn (PASSED)")

    print("\n==================================================")
    print("   TẤT CẢ CÁC BÀI KIỂM THỬ THÀNH CÔNG (SUCCESS)")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
