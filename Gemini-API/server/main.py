"""
FastAPI application entry point for Gemini API Server.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import SERVER_HOST, SERVER_PORT, load_cookies
from .routes.admin import router as admin_router
from .routes.chat import router as chat_router
from .routes.images import router as images_router
from .routes.models import router as models_router
from .schemas import HealthResponse
from .state import set_client

# ─── Lifespan: startup & shutdown ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize GeminiClient on startup, close on shutdown."""
    from gemini_webapi import GeminiClient

    print("\n🚀 Gemini API Server starting...")
    print(f"   Port: {SERVER_PORT}")

    try:
        cookies = load_cookies()
        use_browser_cookies = (
            cookies["psid"] == "" or "PASTE" in cookies["psid"].upper()
        )

        if use_browser_cookies:
            # Auto-import cookies from Chrome (requires admin + browser-cookie3)
            print("   ℹ️  Đang tự động lấy cookie từ Chrome...")
            try:
                import browser_cookie3
                chrome_cookies = browser_cookie3.chrome(domain_name=".google.com")
                psid = ""
                psidts = ""
                for c in chrome_cookies:
                    if c.name == "__Secure-1PSID":
                        psid = c.value
                    elif c.name == "__Secure-1PSIDTS":
                        psidts = c.value

                if not psid:
                    print("\n❌ Không tìm thấy cookie Gemini trong Chrome.")
                    print("   → Hãy đăng nhập vào https://gemini.google.com trên Chrome trước.")
                    raise SystemExit(1)

                client = GeminiClient(
                    secure_1psid=psid,
                    secure_1psidts=psidts,
                    proxy=None,
                )
                print("   ✅ Đã lấy cookie từ Chrome thành công!")

            except ImportError:
                print("\n❌ browser-cookie3 chưa được cài.")
                print("   → Chạy: pip install browser-cookie3")
                raise SystemExit(1)
            except SystemExit:
                raise
            except Exception as e:
                print(f"\n❌ Không thể đọc cookie từ Chrome: {e}")
                print("   → Hãy chạy server với quyền Administrator.")
                raise SystemExit(1)
        else:
            client = GeminiClient(
                secure_1psid=cookies["psid"],
                secure_1psidts=cookies["psidts"],
                proxy=None,
            )

        await client.init(
            timeout=30,
            auto_close=False,
            auto_refresh=True,
        )
        set_client(client)
        print("✅ Gemini client initialized successfully!")
        print(f"   → API docs: http://localhost:{SERVER_PORT}/docs\n")
    except FileNotFoundError as e:
        print(f"\n❌ ERROR: {e}")
        print("   Please create cookies.json in the project root.")
        raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n❌ Failed to initialize Gemini client.")
        print(f"   Error: {e}")
        print()
        print("   Possible fixes:")
        print("   1. Re-login to https://gemini.google.com")
        print("   2. Open DevTools (F12) → Application → Cookies → gemini.google.com")
        print("   3. Double-click the VALUE cell of __Secure-1PSID, Ctrl+A then Ctrl+C")
        print("   4. Paste into cookies.json and restart")
        print()
        raise SystemExit(1)

    yield

    # Shutdown
    print("\n🛑 Gemini API Server shutting down...")


# ─── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Gemini API Server",
    description=(
        "A local OpenAI-compatible API server powered by Google Gemini.\n\n"
        "**Authentication**: Include `Authorization: Bearer <your_api_key>` in all requests.\n\n"
        "**Create API keys**: `POST /admin/keys` with `{\"label\": \"my-app\"}`"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS — allow all origins for local use ────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ───────────────────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(models_router)
app.include_router(images_router)
app.include_router(admin_router)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Check if the server and Gemini client are running."""
    from .state import _client
    return HealthResponse(
        status="ok",
        version="1.0.0",
        gemini_ready=_client is not None,
    )


@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "message": "Gemini API Server is running! 🚀",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "chat": "POST /v1/chat/completions",
            "models": "GET /v1/models",
            "images": "POST /v1/images/generations",
            "create_key": "POST /admin/keys",
        },
    })


# ─── Entrypoint ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
    )
