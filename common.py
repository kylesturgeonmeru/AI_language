"""Shared helpers: paths, run log, atomic writes, and polite HTTP.

Only discover.py and fetch.py import the HTTP helpers. Auth headers and
tokens are never written to the run log or to disk.
"""
import hashlib
import json
import os
import random
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RUN_LOG = DATA / "run_log.jsonl"

CL_BASE = "https://www.courtlistener.com/api/rest/v4/"
CL_STORAGE = "https://storage.courtlistener.com/"

# Venues from the brief, as CourtListener court IDs.
COURTS = ["deb", "njb", "txsb", "txnb", "nysb", "vaeb", "ganb"]
WINDOW_START = "2025-01-01"

# CourtListener limits for this token are 5/min, 50/hour, and 125/day
# (checked 10/09/2026 via /api-usage/). Pacing reads live usage from that
# endpoint; these are the requests we leave unspent in each window.
CL_MARGIN = {60: 0, 3600: 2, 86400: 5}
SEC_MIN_INTERVAL = 0.5  # SEC allows 10 requests/second; we stay far below.

MAX_RETRIES = 5
STOP_AFTER_REFUSALS = 3  # consecutive 403s or 429s before giving up on a source


class SourceStopped(Exception):
    """Raised when a source should not be called again in this run."""


def require_env(*names):
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"Missing required environment variable(s): {', '.join(missing)}. Stopping.")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def atomic_write_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def atomic_write_text(path, text):
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path, obj):
    atomic_write_text(path, json.dumps(obj, indent=2, sort_keys=True) + "\n")


# ---------------------------------------------------------------- run log

def read_log():
    if not RUN_LOG.exists():
        return []
    rows = []
    with open(RUN_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def log_request(url, status, body=None, error=None, source=None, purpose=None):
    row = {
        "url": url,
        "status": status,
        "timestamp": now_iso(),
        "sha256": sha256_bytes(body) if body is not None else None,
        "bytes": len(body) if body is not None else 0,
        "error": error,
        "source": source,
        "purpose": purpose,
    }
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return row


def succeeded_urls():
    return {r["url"] for r in read_log() if r.get("status") == 200 and not r.get("error")}


# ---------------------------------------------------------------- throttling

def cl_usage(http):
    """Live CourtListener usage rows for the user scope.

    The /api-usage/ endpoint has its own throttle (10/min, 120/hour), so
    checking it does not spend the main API budget.
    """
    url = CL_BASE + "api-usage/"
    resp = http.get(url, headers={"Authorization": f"Token {os.environ['COURTLISTENER_TOKEN']}"}, timeout=30)
    log_request(url, resp.status_code, body=resp.content,
                error=None if resp.ok else f"HTTP {resp.status_code}", source="cl_usage")
    resp.raise_for_status()
    return [r for r in resp.json().get("current_usage", []) if r.get("scope") == "user"]


def _cl_wait_seconds(http):
    """Seconds to wait before the next CourtListener API call.

    Returns None when the daily budget is spent, so the caller can stop and
    resume after the rolling window frees up.
    """
    now = datetime.now(timezone.utc)
    wait = 0.0
    for row in cl_usage(http):
        margin = CL_MARGIN.get(row["window_seconds"], 0)
        if row["remaining"] > margin:
            continue
        secs = (datetime.fromisoformat(row["reset_at"]) - now).total_seconds() + 1
        if row["window_seconds"] >= 86400:
            return None
        wait = max(wait, secs)
    return wait


class Session:
    """HTTP session with per-source pacing, backoff, and logging."""

    def __init__(self, max_wait=3700):
        self.http = requests.Session()
        self.max_wait = max_wait  # longest we will sleep for a rolling window
        self.refusals = {}
        self.stopped = set()
        self._last_sec = 0.0

    def _headers(self, source):
        if source == "courtlistener":
            return {"Authorization": f"Token {os.environ['COURTLISTENER_TOKEN']}"}
        if source == "sec":
            return {"User-Agent": os.environ["SEC_USER_AGENT"], "Accept-Encoding": "gzip, deflate"}
        if source == "cl_storage":
            return {"User-Agent": "MERU research (CourtListener RECAP download)"}
        return {}

    def _pace(self, source):
        if source == "courtlistener":
            wait = _cl_wait_seconds(self.http)
            if wait is None:
                raise SourceStopped("CourtListener daily budget spent; rerun after the rolling window frees up.")
            if wait > self.max_wait:
                raise SourceStopped(f"CourtListener needs a {wait:.0f}s wait, over max_wait.")
            if wait > 0:
                print(f"  [pace] waiting {wait:.0f}s for CourtListener rate window", flush=True)
                time.sleep(wait)
        elif source == "sec":
            gap = time.monotonic() - self._last_sec
            if gap < SEC_MIN_INTERVAL:
                time.sleep(SEC_MIN_INTERVAL - gap)
            self._last_sec = time.monotonic()
        elif source == "cl_storage":
            time.sleep(1.0)

    def get(self, url, source, params=None, purpose=None):
        """GET and return the body bytes, or raise. Logs every attempt."""
        if source in self.stopped:
            raise SourceStopped(f"{source} stopped earlier in this run")
        full_url = requests.Request("GET", url, params=params).prepare().url
        for attempt in range(MAX_RETRIES):
            self._pace(source)
            try:
                resp = self.http.get(full_url, headers=self._headers(source), timeout=60)
            except requests.RequestException as e:
                log_request(full_url, None, error=type(e).__name__, source=source, purpose=purpose)
                time.sleep(min(2 ** attempt * 2, 60) + random.random())
                continue
            body = resp.content
            status = resp.status_code
            if status == 200:
                self.refusals[source] = 0
                log_request(full_url, status, body=body, source=source, purpose=purpose)
                return body
            log_request(full_url, status, body=body, error=f"HTTP {status}", source=source, purpose=purpose)
            if status in (403, 429):
                self.refusals[source] = self.refusals.get(source, 0) + 1
                if self.refusals[source] >= STOP_AFTER_REFUSALS:
                    self.stopped.add(source)
                    raise SourceStopped(f"{source}: {self.refusals[source]} consecutive {status}s")
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt * 5
                if delay > self.max_wait:
                    self.stopped.add(source)
                    raise SourceStopped(f"{source}: throttled, Retry-After {delay:.0f}s")
                time.sleep(delay + random.random())
                continue
            if status >= 500:
                time.sleep(min(2 ** attempt * 2, 60) + random.random())
                continue
            raise requests.HTTPError(f"HTTP {status} for {full_url}")
        raise requests.HTTPError(f"Gave up after {MAX_RETRIES} attempts: {full_url}")
