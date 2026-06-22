import os
import time
import json
import urllib.request

def translate_chapter(file_path: str, model: str = "qwen2.5:7b-instruct"):
    if not os.path.exists(file_path):
        print(f"[ERROR] Khong tim thay file: {file_path}")
        return

    print(f"[+] Dang doc file: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Rut gon hien thi doan dau (goc)
    original_lines = content.split("\n")
    original_preview = "\n".join([line for line in original_lines[:15] if line.strip()])

    print("\n============================================================")
    print("   NOI DUNG GOC (TIENG TRUNG - RUT GON 15 DONG DAU)")
    print("============================================================")
    print(original_preview)
    print("============================================================\n")

    print(f"[->] Dang gui yeu cau dich toi Ollama (Model: {model})...")
    print("[i] Thoi gian xu ly co the mat tu 10-30 giay tuy toc do GPU...")

    system_prompt = (
        "Ban la mot dich gia truyen chu chuyen nghiep. Dich doan van ban tieng Trung sau sang tieng Viet.\n"
        "Yeu cau:\n"
        "1. Ban dich thoat y, muot ma, dung van phong truyen chu tieng Viet.\n"
        "2. Giu nguyen dinh dang Markdown va cac ky tu dac biet.\n"
        "3. Khong tu y them bot thong tin."
    )

    payload = {
        "model": model,
        "prompt": f"{system_prompt}\n\nVan ban tieng Trung:\n{content}",
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_predict": 4096
        }
    }

    start_time = time.time()
    
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            translated_text = res_data.get("response", "")
            
        elapsed_time = time.time() - start_time
        
        print("\n============================================================")
        print("   BAN DICH TIENG VIET DAY DU")
        print("============================================================")
        print(translated_text)
        print("============================================================\n")
        print(f"[OK] Hoan thanh dich thuat trong: {elapsed_time:.2f} giay")
        
    except Exception as e:
        print(f"[ERROR] Loi khi goi API Ollama: {e}")

if __name__ == "__main__":
    # Tim file truyen chu tieng Trung trong thu muc mac dinh
    base_dir = "truyen_tai_ve"
    target_file = None
    
    if os.path.exists(base_dir):
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if file.endswith(".md"):
                    target_file = os.path.join(root, file)
                    break
            if target_file:
                break
                
    if not target_file:
        # Neu chua co, tao mot file mau tieng Trung
        print("[i] Khong tim thay file truyen co san, dang tao file test mau...")
        os.makedirs(os.path.join(base_dir, "test_story"), exist_ok=True)
        target_file = os.path.join(base_dir, "test_story", "0001_chuong_test.md")
        sample_content = (
            "# 第9章 不是在梦中的相遇，既非必然也非偶然\n\n"
            "“姐姐你好，我要一杯布丁奶茶，不要布丁，我要减肥。”\n\n"
            "清凉的新开奶茶店，崭新的装修还残留着一些淡淡 of 漆味。\n\n"
            "正直下午，还是上课时间，自然没什么人。\n\n"
            "服务员听到声音后，低了低头，才看到努力踮起脚，却也只能看见一双漂亮眼睛的丫头，登时有些难绷，而后温声说道：“小朋友啊，这个年纪多吃点布丁可以长高哦。”"
        )
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(sample_content)

    translate_chapter(target_file)
