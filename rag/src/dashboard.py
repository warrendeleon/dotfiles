#!/usr/bin/env python3
"""RAG indexer monitoring dashboard. Stdlib-only, read-only."""

import json
import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

DB_PATH = os.path.expanduser("~/.rag/queue.db")
LOG_PATH = os.path.expanduser("~/.rag/logs/indexer.err")
PORT = 7843

# Cache log line count to avoid re-reading the entire file every request.
_log_cache = {"completed": 0, "offset": 0, "last_check": 0}


def _count_completed_incremental():
    """Count 'Completed' lines in the log, resuming from the last read position."""
    now = time.time()
    if now - _log_cache["last_check"] < 2:
        return _log_cache["completed"]

    try:
        with open(LOG_PATH, "r") as f:
            f.seek(_log_cache["offset"])
            new_lines = f.read()
            _log_cache["completed"] += new_lines.count("Completed")
            _log_cache["offset"] = f.tell()
            _log_cache["last_check"] = now
    except FileNotFoundError:
        pass
    return _log_cache["completed"]


def _recent_throughput(window_lines=200):
    """Calculate jobs/minute from the last N log lines."""
    try:
        result = subprocess.run(
            ["tail", f"-{window_lines}", LOG_PATH],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0.0, []

    timestamps = []
    for line in result.stdout.splitlines():
        if "Completed" not in line:
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+", line)
        if m:
            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            timestamps.append(ts)

    if len(timestamps) < 2:
        return 0.0, timestamps

    span_seconds = (timestamps[-1] - timestamps[0]).total_seconds()
    if span_seconds <= 0:
        return 0.0, timestamps

    rate = (len(timestamps) - 1) / (span_seconds / 60)
    return round(rate, 2), timestamps


def _db_stats():
    """Read job counts from the queue DB."""
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status")
        counts = {row["status"]: row["cnt"] for row in cur.fetchall()}

        cur.execute(
            "SELECT file_path FROM jobs WHERE status = 'processing' LIMIT 1"
        )
        row = cur.fetchone()
        current_file = row["file_path"] if row else None

        cur.execute(
            "SELECT file_path, error, attempts FROM jobs "
            "WHERE status = 'failed' ORDER BY rowid DESC LIMIT 5"
        )
        failed = [dict(r) for r in cur.fetchall()]

        conn.close()
    except Exception as e:
        return {"error": str(e)}

    return {
        "pending": counts.get("pending", 0),
        "processing": counts.get("processing", 0),
        "completed_in_db": counts.get("completed", 0),
        "failed": counts.get("failed", 0),
        "current_file": current_file,
        "recent_failures": failed,
    }


def _battery_status():
    """Parse pmset -g batt output."""
    try:
        result = subprocess.run(
            ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}

    output = result.stdout
    source = "AC" if "AC Power" in output else "Battery"

    pct_match = re.search(r"(\d+)%", output)
    pct = int(pct_match.group(1)) if pct_match else None

    charging = "charging" in output and "not charging" not in output
    not_charging = "not charging" in output

    return {
        "source": source,
        "percent": pct,
        "charging": charging,
        "not_charging": not_charging,
    }


def _build_status():
    db = _db_stats()
    rate, _ = _recent_throughput()
    battery = _battery_status()

    completed = db.get("completed_in_db", 0)
    pending = db.get("pending", 0)
    processing = db.get("processing", 0)
    failed = db.get("failed", 0)
    total = completed + pending + processing + failed

    eta_minutes = round(pending / rate) if rate > 0 else None
    if eta_minutes is not None:
        if eta_minutes >= 1440:
            eta_str = f"{eta_minutes // 1440}d {(eta_minutes % 1440) // 60}h"
        elif eta_minutes >= 60:
            eta_str = f"{eta_minutes // 60}h {eta_minutes % 60}m"
        else:
            eta_str = f"{eta_minutes}m"
    else:
        eta_str = "unknown"

    progress_pct = round(completed / total * 100, 1) if total > 0 else 0

    return {
        "completed": completed,
        "pending": pending,
        "processing": processing,
        "failed": failed,
        "total": total,
        "progress_pct": progress_pct,
        "rate_per_min": rate,
        "eta": eta_str,
        "eta_minutes": eta_minutes,
        "current_file": db.get("current_file"),
        "recent_failures": db.get("recent_failures", []),
        "battery": battery,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RAG Indexer</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Mono", Menlo, monospace;
    background: #0d1117; color: #c9d1d9;
    padding: 2rem; max-width: 720px; margin: 0 auto;
  }
  h1 { font-size: 1.1rem; font-weight: 600; margin-bottom: 1.5rem; color: #58a6ff; }
  .progress-wrap {
    background: #161b22; border-radius: 8px; overflow: hidden;
    height: 32px; position: relative; margin-bottom: 0.5rem;
    border: 1px solid #30363d;
  }
  .progress-bar {
    height: 100%; background: #238636; transition: width 0.6s ease;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.8rem; font-weight: 600; color: #fff;
    min-width: 3rem;
  }
  .stats { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 0.75rem; margin: 1.25rem 0; }
  .stat {
    background: #161b22; border: 1px solid #30363d; border-radius: 6px;
    padding: 0.75rem; text-align: center;
  }
  .stat .value { font-size: 1.4rem; font-weight: 700; color: #f0f6fc; }
  .stat .label { font-size: 0.7rem; text-transform: uppercase; color: #8b949e; margin-top: 0.2rem; }
  .row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem; }
  .row .label { color: #8b949e; font-size: 0.8rem; }
  .row .value { font-size: 0.8rem; }
  .section { margin-top: 1.5rem; }
  .section h2 { font-size: 0.85rem; font-weight: 600; color: #8b949e; margin-bottom: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .current-file {
    background: #161b22; border: 1px solid #30363d; border-radius: 6px;
    padding: 0.6rem 0.75rem; font-size: 0.75rem; color: #58a6ff;
    word-break: break-all; overflow: hidden; text-overflow: ellipsis;
  }
  .battery { display: flex; gap: 0.75rem; align-items: center; }
  .battery-icon {
    font-size: 1.2rem; display: flex; align-items: center;
  }
  .failure {
    background: #161b22; border: 1px solid #30363d; border-radius: 6px;
    padding: 0.5rem 0.75rem; margin-bottom: 0.4rem; font-size: 0.72rem;
  }
  .failure .path { color: #f85149; word-break: break-all; }
  .failure .error { color: #8b949e; margin-top: 0.2rem; }
  .meta { font-size: 0.65rem; color: #484f58; margin-top: 1.5rem; text-align: center; }
  .green { color: #3fb950; }
  .yellow { color: #d29922; }
  .red { color: #f85149; }
  .pulse { animation: pulse 2s ease-in-out infinite; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
</style>
</head>
<body>
<h1>RAG Indexer</h1>

<div class="progress-wrap">
  <div class="progress-bar" id="bar" style="width: 0%">0%</div>
</div>
<div class="row">
  <span class="label" id="progress-label">Loading...</span>
  <span class="value" id="eta"></span>
</div>

<div class="stats">
  <div class="stat"><div class="value" id="s-total">-</div><div class="label">Total</div></div>
  <div class="stat"><div class="value green" id="s-completed">-</div><div class="label">Completed</div></div>
  <div class="stat"><div class="value yellow" id="s-pending">-</div><div class="label">Pending</div></div>
  <div class="stat"><div class="value" id="s-rate">-</div><div class="label">Jobs/min</div></div>
</div>

<div class="section" id="current-section" style="display:none">
  <h2>Processing</h2>
  <div class="current-file" id="current-file"></div>
</div>

<div class="section">
  <h2>Power</h2>
  <div class="battery">
    <span class="battery-icon" id="battery-icon"></span>
    <span id="battery-text" class="value">-</span>
  </div>
</div>

<div class="section" id="failures-section" style="display:none">
  <h2>Recent Failures</h2>
  <div id="failures"></div>
</div>

<div class="meta" id="meta">Connecting...</div>

<script>
function shortPath(p) {
  if (!p) return "";
  const home = "__HOME__/";
  if (p.startsWith(home)) p = "~/" + p.slice(home.length);
  if (p.length > 80) p = "..." + p.slice(-77);
  return p;
}

function fmt(n) {
  return n.toLocaleString("en-GB");
}

async function refresh() {
  try {
    const r = await fetch("/api/status");
    const d = await r.json();

    const bar = document.getElementById("bar");
    bar.style.width = d.progress_pct + "%";
    bar.textContent = d.progress_pct + "%";

    document.getElementById("progress-label").textContent =
      fmt(d.completed) + " / " + fmt(d.total);
    document.getElementById("eta").textContent =
      d.eta !== "unknown" ? "ETA " + d.eta : "";

    document.getElementById("s-total").textContent = fmt(d.total);
    document.getElementById("s-completed").textContent = fmt(d.completed);
    document.getElementById("s-pending").textContent = fmt(d.pending);
    document.getElementById("s-rate").textContent = d.rate_per_min;

    const cs = document.getElementById("current-section");
    if (d.current_file) {
      cs.style.display = "";
      const cf = document.getElementById("current-file");
      cf.textContent = shortPath(d.current_file);
      cf.classList.toggle("pulse", d.processing > 0);
    } else {
      cs.style.display = "none";
    }

    const b = d.battery;
    const bi = document.getElementById("battery-icon");
    const bt = document.getElementById("battery-text");
    if (b && b.percent != null) {
      let icon = b.charging ? "⚡" : (b.source === "AC" ? "🔌" : "🔋");
      bi.textContent = icon;
      let state = b.charging ? "charging" : (b.not_charging ? "on AC, not charging" : b.source);
      bt.textContent = b.percent + "% — " + state;
      bt.className = "value " + (b.percent > 50 ? "green" : b.percent > 20 ? "yellow" : "red");
    }

    const fs = document.getElementById("failures-section");
    const fd = document.getElementById("failures");
    if (d.recent_failures && d.recent_failures.length > 0) {
      fs.style.display = "";
      fd.innerHTML = d.recent_failures.map(f =>
        '<div class="failure"><div class="path">' + shortPath(f.file_path) +
        ' (attempt ' + f.attempts + ')</div>' +
        (f.error ? '<div class="error">' + f.error.slice(0, 200) + '</div>' : '') +
        '</div>'
      ).join("");
    } else {
      fs.style.display = "none";
    }

    const ts = new Date(d.timestamp);
    document.getElementById("meta").textContent =
      "Updated " + ts.toLocaleTimeString();
  } catch (e) {
    document.getElementById("meta").textContent = "Error: " + e.message;
  }
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            data = _build_status()
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/":
            body = HTML.replace("__HOME__", str(Path.home())).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Dashboard running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()
