"""
Configuration module for Gemini API Server.
Handles cookie loading, API key management, and server settings.
"""

import json
import os
import secrets
import string
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
COOKIES_FILE = BASE_DIR / "cookies.json"
API_KEYS_FILE = BASE_DIR / "api_keys.json"

# ─── Server Settings ──────────────────────────────────────────────────────────
SERVER_HOST = os.getenv("HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", "7860"))


# ─── Cookie Loading ───────────────────────────────────────────────────────────
def load_cookies() -> dict[str, str]:
    """Load Gemini cookies from cookies.json."""
    if not COOKIES_FILE.exists():
        raise FileNotFoundError(
            f"cookies.json not found at {COOKIES_FILE}.\n"
            "Please create it with your Gemini cookies:\n"
            '{ "__Secure-1PSID": "...", "__Secure-1PSIDTS": "..." }'
        )

    with open(COOKIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support both dict format and array-of-objects format (browser extensions)
    if isinstance(data, list):
        cookies = {item["name"]: item["value"] for item in data if "name" in item}
    else:
        cookies = data

    psid = cookies.get("__Secure-1PSID", "")
    psidts = cookies.get("__Secure-1PSIDTS", "")

    return {"psid": psid, "psidts": psidts}


# ─── API Key Management ───────────────────────────────────────────────────────
def load_api_keys() -> dict[str, str]:
    """Load API keys from api_keys.json. Returns {key: label}."""
    if not API_KEYS_FILE.exists():
        return {}
    with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_api_keys(keys: dict[str, str]) -> None:
    """Save API keys to api_keys.json."""
    with open(API_KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2, ensure_ascii=False)


def generate_api_key(label: str = "default") -> str:
    """Generate a new API key, save it, and return the key string."""
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(40))
    new_key = f"sk-gemini-{random_part}"

    keys = load_api_keys()
    keys[new_key] = label
    save_api_keys(keys)

    return new_key


def list_api_keys() -> dict[str, str]:
    """Return all API keys and their labels."""
    return load_api_keys()


def revoke_api_key(key: str) -> bool:
    """Remove an API key. Returns True if removed, False if not found."""
    keys = load_api_keys()
    if key in keys:
        del keys[key]
        save_api_keys(keys)
        return True
    return False


# ─── CLI Entry Point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "create-key":
        label = sys.argv[2] if len(sys.argv) > 2 else "default"
        key = generate_api_key(label)
        print(f"✅ API key created for '{label}':\n   {key}")

    elif cmd == "list-keys":
        keys = list_api_keys()
        if not keys:
            print("No API keys found.")
        else:
            print(f"{'KEY':<55} LABEL")
            print("-" * 70)
            for k, v in keys.items():
                print(f"{k:<55} {v}")

    elif cmd == "revoke-key":
        if len(sys.argv) < 3:
            print("Usage: python -m server.config revoke-key <api_key>")
        else:
            key = sys.argv[2]
            if revoke_api_key(key):
                print(f"✅ Key revoked: {key}")
            else:
                print(f"❌ Key not found: {key}")

    else:
        print(
            "Gemini API Server — Key Manager\n"
            "\nCommands:\n"
            "  python -m server.config create-key [label]   Create a new API key\n"
            "  python -m server.config list-keys            List all API keys\n"
            "  python -m server.config revoke-key <key>     Revoke an API key\n"
        )
