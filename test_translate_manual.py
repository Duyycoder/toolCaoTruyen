import os
import time
from translator.ollama_translator import OllamaTranslator

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

    print(f"[->] Dang gui yeu cau dich toi Ollama dung OllamaTranslator (Model: {model})...")
    print("[i] Chuong trinh se tu dong chia chunk va kiem tra ro ri chu Trung...")

    # Khoi tao translator voi nguong chuong an toan 1200 ky tu cho moi chunk
    translator = OllamaTranslator(model=model, max_chunk_chars=1200)

    start_time = time.time()
    
    try:
        # Thuc hien dich voi callback log ra console
        translated_text = translator.translate(content, progress_callback=print)
        elapsed_time = time.time() - start_time
        
        print("\n============================================================")
        print("   BAN DICH TIENG VIET DAY DU")
        print("============================================================")
        print(translated_text)
        print("============================================================\n")
        print(f"[OK] Hoan thanh dich thuat trong: {elapsed_time:.2f} giay")
        
    except Exception as e:
        print(f"[ERROR] Loi khi dich thuat: {e}")

if __name__ == "__main__":
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
        print("[ERROR] Khong tim thay file truyen nao de test.")
    else:
        translate_chapter(target_file)
