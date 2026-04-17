#!/usr/bin/env python3
"""Health check: verify all RAG system components are working."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
NC = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{NC} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{NC} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}!{NC} {msg}")


def _expected_embedding_model() -> str:
    """Detect the expected embedding model for this machine."""
    import platform, subprocess
    if platform.system() == "Darwin":
        try:
            ram = int(subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()) / (1024 ** 3)
            chip = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            if "Apple" in chip and ram >= 32:
                return "qwen3-embedding:8b"
        except Exception:
            pass
    return "mxbai-embed-large"


def check_ollama() -> bool:
    """Check if Ollama is running and the expected embedding model is available."""
    print(f"\n{BOLD}Ollama{NC}")

    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
    except Exception:
        fail("Ollama not reachable at localhost:11434")
        return False

    ok("Ollama running")

    expected = _expected_embedding_model()
    if any(expected in m for m in models):
        ok(f"{expected} model available")
        return True
    else:
        fail(f"{expected} not found. Available: {', '.join(models)}")
        warn(f"Run: ollama pull {expected}")
        return False


def check_fswatch() -> bool:
    """Check if fswatch is installed."""
    print(f"\n{BOLD}fswatch{NC}")

    if shutil.which("fswatch"):
        ok("fswatch installed")
        return True
    else:
        fail("fswatch not found")
        warn("Run: brew install fswatch")
        return False


def check_claude_cli() -> bool:
    """Check if Claude CLI is available."""
    print(f"\n{BOLD}Claude CLI{NC}")

    if shutil.which("claude"):
        ok("claude CLI found")
        return True
    else:
        fail("claude CLI not found")
        warn("Run: npm install -g @anthropic-ai/claude-code")
        return False


def check_chromadb() -> bool:
    """Check ChromaDB data directory."""
    print(f"\n{BOLD}ChromaDB{NC}")

    db_path = Path.home() / ".rag" / "chromadb"
    if db_path.exists():
        ok(f"Data directory exists: {db_path}")
    else:
        warn(f"Data directory missing (will be created on first run): {db_path}")

    try:
        from src.store import Store
        store = Store()
        stats = store.stats()
        total = sum(stats.values())
        ok(f"Collections: {stats}")
        ok(f"Total documents: {total}")
        return True
    except Exception as e:
        fail(f"ChromaDB connection failed: {e}")
        return False


def check_queue() -> bool:
    """Check the job queue."""
    print(f"\n{BOLD}Job Queue{NC}")

    queue_path = Path.home() / ".rag" / "queue.db"
    if not queue_path.exists():
        warn("Queue database not found (will be created on first run)")
        return True

    try:
        from src.queue_db import JobQueue
        queue = JobQueue()
        stats = queue.stats()
        ok(f"Queue stats: {stats}")
        pending = stats.get("pending", 0)
        if pending > 100:
            warn(f"{pending} pending jobs — indexer may be behind")
        return True
    except Exception as e:
        fail(f"Queue check failed: {e}")
        return False


def check_audit() -> bool:
    """Check the audit log."""
    print(f"\n{BOLD}Audit Log{NC}")

    try:
        from src.audit import AuditLog
        audit = AuditLog()
        entries = audit.get_entries(limit=1)
        if entries:
            ok(f"Last entry: {entries[0]['description'][:60]}...")
        else:
            warn("No audit entries yet")
        return True
    except Exception as e:
        fail(f"Audit log check failed: {e}")
        return False


def check_launchd() -> bool:
    """Check if launchd services are loaded."""
    print(f"\n{BOLD}launchd Services{NC}")

    all_ok = True
    for label in ("com.dotfiles.rag-watcher", "com.dotfiles.rag-indexer"):
        result = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            ok(f"{label} loaded")
        else:
            warn(f"{label} not loaded")
            all_ok = False

    return all_ok


def check_mcp() -> bool:
    """Check if MCP server is registered."""
    print(f"\n{BOLD}MCP Registration{NC}")

    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        fail("Claude settings.json not found")
        return False

    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        fail(f"Failed to parse settings.json: {e}")
        return False

    # Check for RAG MCP permissions
    allow = settings.get("permissions", {}).get("allow", [])
    rag_perms = [p for p in allow if "mcp__rag" in p]

    if rag_perms:
        ok(f"RAG MCP permissions: {len(rag_perms)} rules")
        return True
    else:
        warn("No RAG MCP permissions found in settings.json")
        return False


def main() -> None:
    print(f"\n{BOLD}RAG System Health Check{NC}")
    print("=" * 40)

    checks = [
        ("Ollama", check_ollama),
        ("fswatch", check_fswatch),
        ("Claude CLI", check_claude_cli),
        ("ChromaDB", check_chromadb),
        ("Job Queue", check_queue),
        ("Audit Log", check_audit),
        ("launchd", check_launchd),
        ("MCP", check_mcp),
    ]

    results = {}
    for name, check_fn in checks:
        try:
            results[name] = check_fn()
        except Exception as e:
            fail(f"{name} check crashed: {e}")
            results[name] = False

    # Summary
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n{'=' * 40}")

    if passed == total:
        print(f"{GREEN}{BOLD}All {total} checks passed{NC}")
    else:
        print(f"{YELLOW}{BOLD}{passed}/{total} checks passed{NC}")
        failed = [name for name, v in results.items() if not v]
        print(f"  Issues: {', '.join(failed)}")


if __name__ == "__main__":
    main()
