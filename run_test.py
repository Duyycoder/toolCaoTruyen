import os
import sys
import json
from translator.ollama_translator import OllamaTranslator
from translator.glossary_manager import GlossaryManager

source_file = r"F:\programfiles\toolCaoTruyen\truyen_tai_ve_test_real\苟成圣人，仙官召我养马\0001_第2章 千年寿命.md"
output_file = r"F:\programfiles\toolCaoTruyen\truyen_tai_ve_test_real\苟成圣人，仙官召我养马\dich_test\0001_第2章 千年寿命_lan3_glossary.md"
story_dir = os.path.dirname(source_file)

os.makedirs(os.path.dirname(output_file), exist_ok=True)

# 1. Khởi tạo Glossary Manager
root_dir = r"F:\programfiles\toolCaoTruyen"
glossary_manager = GlossaryManager(root_dir)
glossary_manager.load_story_glossary(story_dir)

translator = OllamaTranslator(model="qwen3:8b")
if not translator.is_available():
    print("[ERROR] Ollama qwen3:8b không khả dụng. Thử qwen2.5:7b-instruct")
    translator = OllamaTranslator(model="qwen2.5:7b-instruct")

print(f"[INFO] Bắt đầu xử lý với model: {translator.model}...")

# 2. Đọc file gốc và Auto-Extract Glossary
with open(source_file, 'r', encoding='utf-8') as f:
    source_text = f.read()

print("\n[INFO] Đang Auto-Extract Glossary từ văn bản gốc...")
new_terms = translator.extract_glossary_from_text(source_text, glossary_manager.get_combined_glossary())

if new_terms:
    print(f"[INFO] Đã trích xuất được {len(new_terms)} danh từ riêng mới:")
    print(json.dumps(new_terms, indent=4, ensure_ascii=False))
    # Cập nhật và lưu vào file của truyện
    glossary_manager.save_story_glossary(new_terms)
else:
    print("[INFO] Không tìm thấy danh từ riêng nào mới.")

# 3. Nạp Glossary hoàn chỉnh vào Translator
combined_glossary = glossary_manager.get_combined_glossary()
translator.set_glossary(combined_glossary)

print("\n[INFO] Bắt đầu dịch file gốc...")
def log_cb(msg):
    print(f" [Log]: {msg}")

# translator.translate_file(source_file, output_file, progress_callback=log_cb)

print("\n" + "="*60)
print("BÁO CÁO LAST_REPORT:")
print(json.dumps(translator.last_report, indent=4, ensure_ascii=False))
print("="*60)
