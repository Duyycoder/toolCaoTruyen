import os
import sys
import json
import argparse
import zipfile
from typing import List

# Add current folder to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources.registry import get_source
from core.crawler_engine import download_chapters
from translator.glossary_manager import GlossaryManager
from translator import TRANSLATOR_ENGINES, OLLAMA_MODELS

def log_json(event: str, data: dict):
    """Outputs progress log as a JSON string to stdout."""
    print(json.dumps({"event": event, **data}, ensure_ascii=False))
    sys.stdout.flush()

def handle_crawl(args):
    """Subcommand to crawl novel chapters."""
    try:
        source = args.source
        output_dir = os.path.abspath(args.output_dir)

        os.makedirs(output_dir, exist_ok=True)

        log_json("crawl_start", {
            "source": args.source,
            "story_id": args.story_id,
            "start_chapter_id": args.start_chapter_id,
            "num_chapters": args.num_chapters,
            "output_dir": output_dir,
            "continue_download": args.continue_download
        })

        parser = get_source(args.source, args.base_url)

        download_chapters(
            base_url=args.base_url,
            story_id=args.story_id,
            start_chapter_id=args.start_chapter_id,
            num_chapters=args.num_chapters,
            output_dir=output_dir,
            parser=parser,
            continue_download=args.continue_download
        )

        # Create backup _original.zip of all raw crawled chapters
        md_files = [f for f in os.listdir(output_dir) if f.endswith(".md")]
        if md_files:
            zip_path = os.path.join(output_dir, "_original.zip")
            log_json("compress_start", {"zip_path": zip_path, "files_count": len(md_files)})
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f in md_files:
                    fpath = os.path.join(output_dir, f)
                    zipf.write(fpath, f)
            log_json("compress_success", {"zip_path": zip_path})
        else:
            log_json("crawl_warn", {"message": "No chapters downloaded."})

        log_json("crawl_completed", {"status": "success"})
        sys.exit(0)

    except Exception as e:
        log_json("crawl_failed", {"error": str(e)})
        sys.exit(1)

def handle_translate(args):
    """Subcommand to translate novel chapters."""
    try:
        input_dir = os.path.abspath(args.input_dir)
        output_dir = os.path.abspath(args.output_dir)
        engine_type = args.engine
        ollama_model = args.ollama_model
        gemini_api_key = args.gemini_api_key
        gemini_model = args.gemini_model
        gemini_offline_key = args.gemini_offline_key or args.gemini_api_key or "sk-1111"
        gemini_offline_base_url = args.gemini_offline_base_url
        gemini_offline_model = args.gemini_offline_model
        leak_threshold = args.leak_threshold
        genre = args.genre
        auto_extract_glossary = args.auto_extract
        glossary_extract_engine = args.glossary_extract_engine
        glossary_extract_ollama_model = args.glossary_extract_ollama_model

        os.makedirs(output_dir, exist_ok=True)

        # Scan input directory for raw .md files
        if not os.path.isdir(input_dir):
            raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

        # Logic tìm file cần dịch (chỉ lấy các file chưa dịch)
        all_md_files = [f for f in os.listdir(input_dir) if f.endswith(".md") and not f.startswith("_")]
        
        # Tập hợp các prefix của file đã dịch (có chứa [VI])
        translated_prefixes = set()
        for f in all_md_files:
            if " - [VI] " in f:
                prefix = f.split(" - [VI] ")[0]
                translated_prefixes.add(prefix)

        files_to_translate = []
        skipped_already_translated = 0
        for f in all_md_files:
            if " - [VI] " in f:
                continue # Bỏ qua file đã dịch

            # Kiểm tra xem file gốc này đã có bản dịch chưa
            parts = f.split(" - ")
            if len(parts) > 1:
                prefix = parts[0]
                if prefix in translated_prefixes:
                    skipped_already_translated += 1
                    continue # Đã có bản dịch cho prefix này, bỏ qua

            files_to_translate.append(os.path.join(input_dir, f))

        files_to_translate = sorted(files_to_translate)

        if not files_to_translate:
            if skipped_already_translated > 0:
                message = (
                    f"Không có file mới cần dịch: {skipped_already_translated} file gốc "
                    f"đều đã có bản dịch [VI] (có thể do quá trình cào đã tải lại chương cũ)."
                )
            else:
                message = "Không tìm thấy file markdown nào cần dịch trong thư mục."
            log_json("translate_warn", {
                "message": message,
                "total_md_files": len(all_md_files),
                "skipped_already_translated": skipped_already_translated
            })
            sys.exit(0)

        log_json("translate_start", {
            "total_files": len(files_to_translate),
            "engine": engine_type,
            "genre": genre
        })

        # Load Glossary
        glossary_mgr = GlossaryManager(root_dir=".")
        glossary_mgr.load_story_glossary(input_dir)
        combined_glossary = glossary_mgr.get_combined_glossary()

        # Khởi tạo Engine tương ứng
        from translator import TRANSLATOR_ENGINES, OLLAMA_MODELS

        if engine_type == "ollama":
            chunk_size = OLLAMA_MODELS.get(ollama_model, {}).get("chunk_size_chars", 350)
            translator = TRANSLATOR_ENGINES["ollama"](
                model=ollama_model,
                max_chunk_chars=chunk_size,
                leak_threshold_percent=leak_threshold
            )
        elif engine_type == "gemini":
            translator = TRANSLATOR_ENGINES["gemini"](
                api_key=gemini_api_key,
                model=gemini_model,
                leak_threshold_percent=leak_threshold
            )
        elif engine_type == "gemini_api":
            translator = TRANSLATOR_ENGINES["gemini_api"](
                api_key=gemini_offline_key,
                base_url=gemini_offline_base_url,
                model=gemini_offline_model,
                leak_threshold_percent=leak_threshold
            )
        else:
            raise ValueError(f"Invalid engine type: {engine_type}")

        # Khởi tạo glossary_extractor độc lập dựa trên cấu hình chọn mô hình trích xuất
        glossary_extractor = None
        if auto_extract_glossary:
            if glossary_extract_engine == "same_as_trans":
                glossary_extractor = translator
            elif glossary_extract_engine == "gemini":
                if engine_type == "gemini":
                    glossary_extractor = translator
                elif gemini_api_key and gemini_api_key.strip():
                    try:
                        glossary_extractor = TRANSLATOR_ENGINES["gemini"](
                            api_key=gemini_api_key,
                            model=gemini_model,
                            leak_threshold_percent=leak_threshold
                        )
                    except Exception as e:
                        print(f"[WARN] Không thể khởi tạo gemini_extractor độc lập: {e}")
            elif glossary_extract_engine == "ollama":
                model_to_use = glossary_extract_ollama_model or ollama_model
                if engine_type == "ollama" and model_to_use == ollama_model:
                    glossary_extractor = translator
                else:
                    try:
                        chunk_size = OLLAMA_MODELS.get(model_to_use, {}).get("chunk_size_chars", 350)
                        glossary_extractor = TRANSLATOR_ENGINES["ollama"](
                            model=model_to_use,
                            max_chunk_chars=chunk_size,
                            leak_threshold_percent=leak_threshold
                        )
                    except Exception as e:
                        print(f"[WARN] Không thể khởi tạo Ollama extractor độc lập cho '{model_to_use}': {e}")
            elif glossary_extract_engine == "gemini_api":
                if engine_type == "gemini_api":
                    glossary_extractor = translator
                else:
                    try:
                        glossary_extractor = TRANSLATOR_ENGINES["gemini_api"](
                            api_key=gemini_offline_key,
                            base_url=gemini_offline_base_url,
                            model=gemini_offline_model,
                            leak_threshold_percent=leak_threshold
                        )
                    except Exception as e:
                        print(f"[WARN] Không thể khởi tạo gemini_offline_extractor độc lập: {e}")

        # Cấu hình Genre cho các translator/extractor
        translator.set_genre(genre)
        if glossary_extractor:
            glossary_extractor.set_genre(genre)

        # Load idioms
        common_idioms_path = os.path.join(".", "common_idioms.json")
        if os.path.exists(common_idioms_path):
            with open(common_idioms_path, 'r', encoding='utf-8') as f:
                idioms = json.load(f)
                translator.set_common_idioms(idioms)
                if glossary_extractor:
                    glossary_extractor.set_common_idioms(idioms)

        translator.set_glossary(combined_glossary)

        # Model chuyên dịch (MT) không làm được trích xuất JSON -> bỏ qua auto-extract;
        # glossary có sẵn (global + story) vẫn được áp dụng qua template thuật ngữ
        translator_prompt_style = getattr(translator, "prompt_style", "chat")
        if auto_extract_glossary and glossary_extractor is None and translator_prompt_style != "chat":
            auto_extract_glossary = False
            log_json("file_log", {
                "message": f"Model chuyên dịch ({translator_prompt_style}) không hỗ trợ trích xuất từ điển tự động — bỏ qua bước trích xuất. Glossary có sẵn vẫn được áp dụng khi dịch."
            })

        if auto_extract_glossary:
            extract_engine_name = glossary_extract_engine
            if extract_engine_name == "same_as_trans":
                extract_engine_name = engine_type
            log_json("file_log", {"message": f"Trích xuất từ điển tự động chạy bằng engine: {extract_engine_name}"})

        # Translation execution loop
        for idx, file_path in enumerate(files_to_translate, 1):
            file_name = os.path.basename(file_path)

            # Chống trùng lặp: nếu chương này đã có bản dịch [VI] trong thư mục đích
            # thì ghi đè lên file đó thay vì tạo thêm một bản dịch với tên khác
            chapter_prefix = file_name.split(" - ")[0]
            existing_translation = None
            for g in sorted(os.listdir(output_dir)):
                if g.endswith(".md") and " - [VI] " in g and g.split(" - [VI] ")[0] == chapter_prefix:
                    existing_translation = g
                    break

            # Simple wrapper to translate filename
            import asyncio
            from app import translate_filename_fn
            if existing_translation:
                translated_file_name = existing_translation
                log_json("file_log", {"message": f"Chương '{chapter_prefix}' đã có bản dịch cũ, sẽ ghi đè: {existing_translation}"})
            else:
                # Run coroutine synchronously
                translated_file_name = asyncio.run(translate_filename_fn(file_name, translator))
            output_path = os.path.join(output_dir, translated_file_name)

            log_json("file_start", {
                "index": idx,
                "total": len(files_to_translate),
                "original": file_name,
                "translated": translated_file_name
            })

            # Auto extract glossary from first 1500 chars of chapter
            if auto_extract_glossary:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text_content = f.read()
                    if text_content.strip():
                        extractor = glossary_extractor if (glossary_extractor and glossary_extractor.is_available()) else translator
                        new_terms = extractor.extract_glossary_from_text(text_content, translator.glossary)
                        if new_terms:
                            added_story = glossary_mgr.save_story_glossary(new_terms)
                            added_global = glossary_mgr.save_global_glossary(new_terms)
                            if added_story > 0 or added_global > 0:
                                updated_glossary = glossary_mgr.get_combined_glossary()
                                translator.set_glossary(updated_glossary)
                                log_json("glossary_added", {
                                    "new_terms": new_terms,
                                    "added_story": added_story,
                                    "added_global": added_global
                                })
                except Exception as ex:
                    log_json("glossary_warn", {"error": str(ex)})

            # Translate file content
            translator.translate_file(file_path, output_path, progress_callback=lambda msg: log_json("file_log", {"message": msg}))

            # Nếu ghi đè bản dịch cũ thì audio cũ không còn khớp nội dung -> xóa để TTS tạo lại
            if existing_translation:
                for audio_ext in (".wav", ".mp3"):
                    stale_audio = os.path.splitext(output_path)[0] + audio_ext
                    if os.path.exists(stale_audio):
                        try:
                            os.remove(stale_audio)
                            log_json("file_log", {"message": f"Đã xóa audio cũ không còn khớp: {os.path.basename(stale_audio)}"})
                        except OSError as ex:
                            log_json("cleanup_warn", {"file": os.path.basename(stale_audio), "error": str(ex)})

            report = getattr(translator, "last_report", {})
            failed_p = len(report.get("failed_chunks", []))
            total_p = report.get("total_paras", 0)

            # Tự động dịch vá các đoạn lỗi ([[MISSING_CHUNK]]) và ghép lại vào file
            # Thử tối đa 3 vòng: mỗi vòng Ollama dịch lại các đoạn còn marker
            MAX_REPAIR_ROUNDS = 3
            if failed_p > 0:
                for repair_round in range(1, MAX_REPAIR_ROUNDS + 1):
                    log_json("file_repair_start", {
                        "index": idx,
                        "file": translated_file_name,
                        "failed_paragraphs": failed_p,
                        "round": repair_round,
                        "max_rounds": MAX_REPAIR_ROUNDS
                    })
                    try:
                        remaining = translator.repair_missing_chunks(
                            output_path,
                            progress_callback=lambda msg: log_json("file_log", {"message": msg})
                        )
                        repaired_this_round = failed_p - remaining
                        log_json("file_repair_done", {
                            "index": idx,
                            "file": translated_file_name,
                            "round": repair_round,
                            "repaired": repaired_this_round,
                            "still_failed": remaining
                        })
                        failed_p = remaining
                        if failed_p == 0:
                            break  # Tất cả đã được vá
                        if repaired_this_round == 0 and repair_round >= 2:
                            # 2 vòng liên tiếp không vá thêm được → dừng sớm
                            log_json("file_log", {
                                "message": f"Dừng vá sớm sau vòng {repair_round}: không vá thêm được đoạn nào."
                            })
                            break
                    except Exception as ex:
                        log_json("file_repair_warn", {"file": translated_file_name, "error": str(ex), "round": repair_round})
                        break


            if failed_p > 0:
                log_json("file_failed", {
                    "index": idx,
                    "file": translated_file_name,
                    "failed_paragraphs": failed_p,
                    "total_paragraphs": total_p
                })
                # If there are failed chunks, we don't delete the original file so user can retry/debug
            else:
                log_json("file_success", {
                    "index": idx,
                    "file": translated_file_name,
                    "total_paragraphs": total_p
                })
                # Clean up raw Chinese/English markdown file since it's successfully translated
                # and already backed up in _original.zip
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        log_json("cleanup_file", {"file": file_name})
                    except OSError as ex:
                        log_json("cleanup_warn", {"file": file_name, "error": str(ex)})

        log_json("translate_completed", {"status": "success"})
        sys.exit(0)

    except Exception as e:
        log_json("translate_failed", {"error": str(e)})
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Non-interactive CLI Adapter for toolCaoTruyen")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Crawl Subcommand
    crawl_parser = subparsers.add_parser("crawl", help="Crawl chapters from online source")
    crawl_parser.add_argument("--source", default="69shuba", help="Source registry name")
    crawl_parser.add_argument("--base-url", default="https://www.69shuba.com/txt", help="Base site URL")
    crawl_parser.add_argument("--story-id", required=True, help="Story ID or starting URL")
    crawl_parser.add_argument("--start-chapter-id", default="Auto", help="Start chapter ID or URL. 'Auto' uses the first chapter.")
    crawl_parser.add_argument("--num-chapters", type=int, default=10, help="Number of chapters to crawl.")
    crawl_parser.add_argument("--output-dir", required=True, help="Directory to save raw chapters.")
    crawl_parser.add_argument("--continue-download", action="store_true", help="Continue download from last saved chapter.")
    crawl_parser.set_defaults(func=handle_crawl)

    # Translate Subcommand
    translate_parser = subparsers.add_parser("translate", help="Translate raw chapters to Vietnamese")
    translate_parser.add_argument("--input-dir", required=True, help="Directory containing raw chapters")
    translate_parser.add_argument("--output-dir", required=True, help="Directory to save translated chapters")
    translate_parser.add_argument("--engine", default="gemini_api", choices=["ollama", "gemini", "gemini_api"], help="Translator engine")
    translate_parser.add_argument("--ollama-model", default="qwen2.5:7b-instruct", help="Ollama model name")
    translate_parser.add_argument("--gemini-api-key", default="", help="Gemini API Key")
    translate_parser.add_argument("--gemini-model", default="gemini-2.5-flash", help="Gemini model name")
    translate_parser.add_argument("--gemini-offline-key", default="", help="Gemini offline key")
    translate_parser.add_argument("--gemini-offline-base-url", default="http://localhost:7860/v1", help="Gemini offline base URL")
    translate_parser.add_argument("--gemini-offline-model", default="gemini-2.5-flash", help="Gemini offline model name")
    translate_parser.add_argument("--leak-threshold", type=int, default=10, help="Leak threshold percentage")
    translate_parser.add_argument("--genre", default="tien_hiep", help="Novel genre")
    translate_parser.add_argument("--auto-extract", action="store_true", default=True, help="Auto extract glossary")
    translate_parser.add_argument("--glossary-extract-engine", default="gemini", choices=["gemini", "ollama", "gemini_api", "same_as_trans"], help="Glossary extraction engine")
    translate_parser.add_argument("--glossary-extract-ollama-model", default="", help="Glossary extraction Ollama model name")
    translate_parser.set_defaults(func=handle_translate)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
