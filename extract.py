"""Extract: PDF text to data/text/, with an OCR fallback for scanned pages.

Reads only saved files. Each PDF under data/raw/ becomes a .txt file at the
same relative path under data/text/, with "=== page N ===" markers so later
stages can cite page numbers, and a blank line between layout blocks so
later stages can split paragraphs. A PDF whose text layer is mostly empty is run
through ocrmypdf when it is installed; otherwise it is flagged needs_ocr.

Usage: python extract.py
"""
import csv
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf

from common import DATA, atomic_write_text, sha256_bytes

RAW = DATA / "raw"
TEXT = DATA / "text"
MANIFEST = DATA / "text_manifest.csv"
FIELDS = ["pdf", "text", "pdf_sha256", "pages", "chars", "empty_pages", "method", "status", "version"]
VERSION = "blocks-1"  # bump to force re-extraction when the method changes
MIN_PAGE_CHARS = 50  # a page with less text than this is treated as scanned


def page_text(page):
    """Text of one page with a blank line between layout blocks (roughly paragraphs)."""
    blocks = [b[4].strip() for b in page.get_text("blocks", sort=True) if b[6] == 0 and b[4].strip()]
    return "\n\n".join(blocks)


def page_texts(pdf_path):
    with pymupdf.open(pdf_path) as doc:
        return [page_text(p) for p in doc]


def ocr(pdf_path):
    """Return OCRed page texts, or None if ocrmypdf is unavailable or fails."""
    if not shutil.which("ocrmypdf"):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "ocr.pdf"
        res = subprocess.run(["ocrmypdf", "--skip-text", "--quiet", str(pdf_path), str(out)],
                             capture_output=True)
        return page_texts(out) if res.returncode == 0 and out.exists() else None


def render(pages):
    return "".join(f"=== page {i} ===\n{t.rstrip()}\n\n" for i, t in enumerate(pages, 1))


def main():
    old = {}
    if MANIFEST.exists():
        with open(MANIFEST, newline="", encoding="utf-8") as f:
            old = {r["pdf"]: r for r in csv.DictReader(f)}
    rows, counts = [], {"skipped": 0, "extracted": 0, "ocr": 0, "needs_ocr": 0}
    for pdf in sorted(RAW.rglob("*.pdf")):
        rel = str(pdf.relative_to(DATA.parent))
        txt = TEXT / pdf.relative_to(RAW).with_suffix(".txt")
        sha = sha256_bytes(pdf.read_bytes())
        prev = old.get(rel)
        if prev and prev["pdf_sha256"] == sha and txt.exists() and prev["status"] == "ok" \
                and prev.get("version") == VERSION:
            rows.append(prev)
            counts["skipped"] += 1
            continue
        pages = page_texts(pdf)
        empty = sum(1 for t in pages if len(t.strip()) < MIN_PAGE_CHARS)
        method, status = "text", "ok"
        if pages and empty / len(pages) > 0.5:
            ocred = ocr(pdf)
            if ocred:
                pages, method = ocred, "ocr"
                empty = sum(1 for t in pages if len(t.strip()) < MIN_PAGE_CHARS)
                counts["ocr"] += 1
            else:
                status = "needs_ocr"
                counts["needs_ocr"] += 1
        atomic_write_text(txt, render(pages))
        rows.append({"pdf": rel, "text": str(txt.relative_to(DATA.parent)), "pdf_sha256": sha,
                     "pages": len(pages), "chars": sum(len(t) for t in pages), "empty_pages": empty,
                     "method": method, "status": status, "version": VERSION})
        counts["extracted"] += 1
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    atomic_write_text(MANIFEST, buf.getvalue())
    print(f"{len(rows)} PDFs: {counts}")


if __name__ == "__main__":
    main()
