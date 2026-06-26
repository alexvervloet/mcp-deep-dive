"""
Setup check — run this first.
=============================

    python check_setup.py

Checks your Python version, the installed packages (the `mcp` SDK above all),
your chosen PROVIDER, and the API key that provider needs — and tells you
exactly what to fix. Makes NO API calls. Uses only the standard library, so it
runs even before `pip install`.

Note the split: the `mcp` SDK and a 3.10+ Python are required for EVERYTHING.
A PROVIDER and its key are required ONLY for the LLM-in-the-loop sections
(8 + the capstone). The whole point of MCP-first learning is that a server and
a client can talk with no model at all — so this check will still cheer you on
to the offline examples even if you have no key yet.
"""

import importlib.util
import os
import sys

_USE_COLOR = sys.stdout.isatty() and os.getenv("NO_COLOR") is None


def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def ok(msg):
    print(f"  {_c('✓', '32')} {msg}")


def warn(msg):
    print(f"  {_c('!', '33')} {msg}")


def fail(msg):
    print(f"  {_c('✗', '31')} {msg}")


HERE = os.path.dirname(os.path.abspath(__file__))


def _read_env_file():
    env_path = os.path.join(HERE, ".env")
    values = {}
    if not os.path.exists(env_path):
        return None
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def _get(env, name):
    return os.getenv(name) or (env or {}).get(name, "")


# The mcp SDK is the one hard requirement for the whole repo.
CORE = [
    ("mcp", "mcp", "the Model Context Protocol SDK — the whole point of this repo"),
]
# Needed only once you put an LLM in the loop (Section 8 + capstone).
HOST = [
    ("dotenv", "python-dotenv", "loads your key from .env (host sections)"),
]
PROVIDER_DEPS = {
    "openai": [("openai", "openai", "OpenAI chat + function calling (host sections)")],
    "claude": [("anthropic", "anthropic", "Claude messages + tool use (host sections)")],
}
PROVIDER_KEYS = {
    "openai": [("OPENAI_API_KEY", "sk-", "sk-your-openai-key-here")],
    "claude": [("ANTHROPIC_API_KEY", "sk-ant-", "sk-ant-your-key-here")],
}


def check_python():
    print("Python version")
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 10):
        ok(f"Python {major}.{minor} (3.10+ required by the mcp SDK)")
        return True
    fail(f"Python {major}.{minor} — this repo needs Python 3.10 or newer.")
    print("    Install a newer Python from https://www.python.org/downloads/")
    return False


def check_core():
    print("\nCore dependency (required for everything)")
    missing = []
    for import_name, pip_name, purpose in CORE:
        if importlib.util.find_spec(import_name) is not None:
            ok(f"{pip_name} — {purpose}")
        else:
            fail(f"{pip_name} MISSING — {purpose}")
            missing.append(pip_name)
    if missing:
        print("\n    Install everything with:")
        print("        pip install -r requirements.txt")
    return not missing


def check_provider(env):
    print("\nProvider (only needed for the LLM-in-the-loop sections)")
    provider = (_get(env, "PROVIDER") or "openai").strip().lower()
    if provider in PROVIDER_DEPS:
        ok(f"PROVIDER = {provider}")
        return provider
    warn(f"PROVIDER = {provider!r} is not recognized.")
    print("    Set PROVIDER=openai or PROVIDER=claude in .env (only matters for Section 8+).")
    return None


def check_host_deps(provider):
    print("\nHost dependencies (only needed for the LLM-in-the-loop sections)")
    needed = HOST + PROVIDER_DEPS.get(provider, [])
    missing = []
    for import_name, pip_name, purpose in needed:
        if importlib.util.find_spec(import_name) is not None:
            ok(f"{pip_name} — {purpose}")
        else:
            warn(f"{pip_name} not installed — {purpose}")
            missing.append(pip_name)
    if missing:
        print("\n    Install everything (incl. the host deps) with:")
        print("        pip install -r requirements.txt")
    return not missing


def check_keys(env, provider):
    print("\nAPI key (only needed for the LLM-in-the-loop sections)")
    if env is None:
        warn(".env file not found — fine for the offline sections.")
        print("    When you reach Section 8, create it with:  cp .env.example .env")
        return False
    if provider is None:
        return False
    all_ok = True
    for name, prefix, placeholder in PROVIDER_KEYS.get(provider, []):
        value = _get(env, name)
        if not value or value == placeholder:
            warn(f"{name} is not set (still the placeholder).")
            print("    Needed only for Section 8+. Open .env and paste your real key when you get there.")
            all_ok = False
        elif not value.startswith(prefix):
            warn(f"{name} is set but doesn't start with '{prefix}'. Double-check it.")
        else:
            ok(f"{name} is set and looks right.")
    return all_ok


def main():
    print(_c("Checking your setup for the MCP deep dive...\n", "1"))
    env = _read_env_file()
    py = check_python()
    core = check_core()
    provider = check_provider(env)
    check_host_deps(provider)
    keys = check_keys(env, provider)

    print()
    if py and core:
        print(_c("Ready for the offline sections! 🎉", "1;32"))
        print("Start here (no key, no cost):")
        print("    python examples/01_protocol.py")
        print("    python examples/03_client_calls_tool.py   # a server and client actually talk")
        if not keys:
            print("\nWhen you reach Section 8 (LLM in the loop), set PROVIDER + its key in .env.")
        return 0
    print(_c("Not ready yet — fix the ✗ items above, then run this again.", "1;31"))
    print("(The ✗ items are the hard requirements: Python 3.10+ and the `mcp` SDK.)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
