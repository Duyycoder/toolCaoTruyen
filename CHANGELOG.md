# Changelog

All notable changes to this project will be documented in this file.

---

## [Phase B-FINAL] - 2026-06-23
### Added
- **Gemini API Integration**: Implemented `GeminiTranslator` calling Google's Gemini REST API (`gemini-2.5-flash`) via Python's built-in `urllib` standard library.
- **Model & Engine Selector Registry**: Created `translator/registry.py` to map translation engines ("ollama", "gemini") and model configurations (e.g. `qwen2.5:7b-instruct`, `qwen3:8b`).
- **Web UI Translation Tab**: Designed and implemented a dedicated "Dịch Truyện Offline" tab in `index.html` using a premium CSS styling system.
- **System File Dialogs**: Added `/api/select-files` to select multiple Markdown files for translation natively.
- **Dynamic Source Language Prompts**: Added `build_system_prompt` supporting Chinese, Japanese, Korean, and English.
- **Tier 2 Paragraph Repair**: Implemented a post-processing pass to scan and repair Chinese character leakages at chunk boundaries.
- **pytests / unit tests**: Created comprehensive mock unit tests in `test_translator_unit.py` and achieved 100% pass rate.

### Changed
- **Config Schema Migration**: Automatically migrates `config.json` to support nested `"translator"` configuration blocks.
- **Ollama Translator Refactor**: Made `OllamaTranslator` inherit from `TranslatorEngine` and dynamically check model availability via Ollama's `/api/tags` endpoint.
- **Documentation**: Updated `README.md` with instructions for engine/model selection, Gemini API key registration, and descriptions of the warning markers.

---

## [Phase B1-FIX] - 2026-06-22
### Added
- **Paragraph Chunking**: Implemented `split_text_into_chunks` dividing Chinese web novel chapters strictly along `\n\n` boundaries.
- **Leak Detection**: Implemented `contains_chinese_leak` using regex patterns to find residual Han characters in outputs.
- **Ollama Chat API**: Switched from Generate API `/api/generate` to Chat API `/api/chat` for superior instruction adherence.

---

## [Phase A3] - 2026-06-21
### Added
- **Real-time Progress Websocket**: Created `/ws/crawl` delivering download status, chapter counts, delays, and exceptions to the Web UI.
- **Asynchronous Execution Threading**: Integrated `asyncio.to_thread` to execute blocking Selenium calls without interrupting uvicorn's event loop.

---

## [Phase A2] - 2026-06-20
### Added
- **FastAPI Web UI**: Created `app.py` serving a clean dark-themed index page with uvicorn.
- **System Directory Selector**: Integrated Tkinter dialogs in `ask_directory_sync` to allow browsing output folders.

---

## [Phase A1] - 2026-06-19
### Changed
- **Core Package Extraction**: Separated core business logic out of `main.py` into `core/config_manager.py` and `core/crawler_engine.py` to prevent duplicate code.

---

## [Phase 1] - 2026-06-18
### Changed
- **Strategy Pattern Refactor**: Restructured source parsers under `sources/` using a parser strategy pattern. Unified driver instantiation and execution context.

---

## [Phase 0] - 2026-06-17
### Added
- **Baseline Git Commit**: Initial baseline code auditing of `main.py`.
- **Architectural Plan**: Created `PLAN.md` documenting core dependencies and refactoring risks.
