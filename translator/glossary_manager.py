import os
import json

class GlossaryManager:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.global_glossary_path = os.path.join(self.root_dir, "global_glossary.json")
        self.global_glossary = self._load_json(self.global_glossary_path)
        self.story_glossary = {}
        self.story_glossary_path = None

    def _load_json(self, path: str) -> dict:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Warning] Không thể nạp glossary từ {path}: {e}")
        return {}

    def load_story_glossary(self, story_dir: str):
        self.story_glossary_path = os.path.join(story_dir, "glossary.json")
        self.story_glossary = self._load_json(self.story_glossary_path)

    def get_combined_glossary(self) -> dict:
        """
        Trả về từ điển đã gộp. Ưu tiên Per-Story Glossary nếu có key trùng.
        """
        combined = self.global_glossary.copy()
        combined.update(self.story_glossary)
        return combined

    def save_story_glossary(self, new_terms: dict) -> int:
        """
        Thêm các từ mới vào story glossary và lưu xuống file.
        Chỉ lưu nếu key chưa tồn tại.
        Trả về số lượng từ mới đã được thêm.
        """
        if not self.story_glossary_path:
            print("[Warning] Chưa khởi tạo story glossary path.")
            return 0
            
        added_count = 0
        for k, v in new_terms.items():
            if k not in self.story_glossary:
                self.story_glossary[k] = v
                added_count += 1
                
        if added_count > 0:
            try:
                # Đảm bảo thư mục tồn tại
                os.makedirs(os.path.dirname(self.story_glossary_path), exist_ok=True)
                with open(self.story_glossary_path, 'w', encoding='utf-8') as f:
                    json.dump(self.story_glossary, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"[Error] Không thể lưu story glossary: {e}")
                
        return added_count

    def save_global_glossary(self, new_terms: dict) -> int:
        """
        Thêm các từ mới vào global glossary và lưu xuống file.
        Chỉ lưu nếu key chưa tồn tại để tránh rò rỉ từ dịch sai từ LLM.
        Trả về số lượng từ mới đã được thêm.
        """
        added_count = 0
        for k, v in new_terms.items():
            if k not in self.global_glossary:
                self.global_glossary[k] = v
                added_count += 1
                
        if added_count > 0:
            try:
                with open(self.global_glossary_path, 'w', encoding='utf-8') as f:
                    json.dump(self.global_glossary, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"[Error] Không thể lưu global glossary: {e}")
                
        return added_count
