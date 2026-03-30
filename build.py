#!/usr/bin/env python3
"""
build.py — String Theory Chapter Site Builder
─────────────────────────────────────────────
Reads the master TXT export from Google Drive / Manuscript Masters,
splits on |  N  | chapter markers (and |  Overture  |), and generates:

  /chapters/overture.html                           — overture / prologue
  /chapters/chapter-01.html ... chapter-NN.html     — one page per chapter
  /edits/                                           — empty dir for LLM edits
  /index.html                                       — master chapter list
  /llm-interface.html                               — LLM usage guide + API reference

Triggered by pages_tagged_export.sh after each export.

Usage:
    python3 build.py [path_to_txt_file]
    python3 build.py   (uses default Manuscript Masters path)
"""

import os
import re
import sys
import json
import html
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
GDRIVE = Path.home() / "Library/CloudStorage/GoogleDrive-gabemcpherson@gmail.com/My Drive/Manuscript Masters"
DEFAULT_TXT = GDRIVE / "String Theory - Draft 6.6.txt"
OUT_DIR = Path(__file__).parent
CHAPTER_DIR = OUT_DIR / "chapters"
EDITS_DIR   = OUT_DIR / "edits"
REPO        = "Gabrielmcp78/string-theory-chapters"
PAGES_URL   = "https://gabrielmcp78.github.io/string-theory-chapters"
BOOK_TITLE  = "String Theory"
AUTHOR      = "Gabriel McPherson"

# Chapter marker: | N | for numbered chapters, | Overture | or | Prologue | for front matter
# Overture/Prologue are treated as chapter 0 internally and get slug "overture"
CHAPTER_RE  = re.compile(r'^\s*\|\s*(\d+|Overture|Prologue)\s*\|\s*$', re.MULTILINE | re.IGNORECASE)

# ── CSS shared across all pages ───────────────────────────────────────────────
CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 1.1rem;
    line-height: 1.85;
    color: #1a1a1a;
    background: #fafaf8;
    max-width: 720px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
}
header {
    border-bottom: 1px solid #ddd;
    padding-bottom: 1rem;
    margin-bottom: 2rem;
}
header .book-title { font-size: 0.85rem; color: #888; letter-spacing: 0.08em; text-transform: uppercase; }
h1 { font-size: 1.5rem; font-weight: normal; margin: 0.3rem 0; }
nav { margin-top: 0.6rem; font-size: 0.9rem; }
nav a { color: #555; text-decoration: none; margin-right: 1.2rem; }
nav a:hover { text-decoration: underline; }
.chapter-text p { margin-bottom: 1.2em; }
.chapter-text p:first-child::first-letter {
    font-size: 3.2em; float: left; line-height: 0.75;
    margin: 0.1em 0.07em 0 0; font-family: Georgia, serif;
}
.chapter-number { font-size: 0.8rem; color: #aaa; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 0.3rem; }
.chapter-heading { font-size: 1.7rem; font-weight: normal; margin-bottom: 0.5rem; }
.chapter-subheading { font-size: 0.95rem; color: #666; font-style: italic; margin-bottom: 2rem; }
.edit-bar {
    background: #f0f0ec;
    border: 1px solid #ddd;
    border-radius: 6px;
    padding: 0.8rem 1rem;
    margin-bottom: 2rem;
    font-size: 0.85rem;
    color: #555;
}
.edit-bar a { color: #2563eb; text-decoration: none; }
.edit-bar a:hover { text-decoration: underline; }
footer {
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid #eee;
    font-size: 0.8rem;
    color: #aaa;
    display: flex;
    justify-content: space-between;
}
footer a { color: #aaa; }
/* Index page */
.chapter-list { list-style: none; }
.chapter-list li { padding: 0.6rem 0; border-bottom: 1px solid #eee; }
.chapter-list li:last-child { border-bottom: none; }
.chapter-list a { text-decoration: none; color: #1a1a1a; font-size: 1.05rem; }
.chapter-list a:hover { color: #2563eb; }
.chapter-list .ch-num { color: #aaa; font-size: 0.85rem; min-width: 3.5rem; display: inline-block; }
.meta { font-size: 0.85rem; color: #888; margin-top: 0.3rem; }
.tag { display: inline-block; background: #eef2ff; color: #4f46e5; border-radius: 4px;
       padding: 0.15rem 0.5rem; font-size: 0.75rem; margin-right: 0.4rem; }
"""

def slugify(n):
    """Return filename stem for a chapter number.
    0 (Overture/Prologue) → 'overture'
    N → 'chapter-NN'
    """
    if n == 0:
        return "overture"
    return f"chapter-{int(n):02d}"

def chapter_label(n):
    """Human-readable chapter label for display."""
    if n == 0:
        return "Overture"
    return f"Chapter {n}"

def chapter_nav_label(n):
    """Short label for prev/next navigation links."""
    if n == 0:
        return "Overture"
    return f"Ch {n}"

def text_to_paragraphs(raw):
    """Convert raw text lines to HTML paragraphs."""
    paras = []
    buf = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped:
            buf.append(stripped)
        else:
            if buf:
                paras.append(' '.join(buf))
                buf = []
    if buf:
        paras.append(' '.join(buf))
    return ''.join(f'<p>{html.escape(p)}</p>\n' for p in paras if p)

def parse_chapters(txt_path):
    """Return list of (chapter_number, raw_text) tuples.
    Overture/Prologue markers are converted to chapter number 0.
    """
    text = Path(txt_path).read_text(encoding='utf-8', errors='replace')
    matches = list(CHAPTER_RE.finditer(text))
    chapters = []
    for i, m in enumerate(matches):
        raw = m.group(1)
        num = 0 if raw.lower() in ('overture', 'prologue') else int(raw)
        start = m.end()
        end   = matches[i+1].start() if i+1 < len(matches) else len(text)
        body  = text[start:end].strip()
        chapters.append((num, body))
    return chapters

def extract_heading(body):
    """Pull first non-empty lines as title / subheading."""
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    title    = lines[0] if lines else ""
    subtitle = lines[1] if len(lines) > 1 else ""
    rest_start = body.find(lines[2] if len(lines) > 2 else lines[-1]) if len(lines) > 2 else len(body)
    rest = body[rest_start:] if len(lines) > 2 else "\n".join(lines[2:])
    return title, subtitle, rest

def make_chapter_html(num, body, all_nums, build_date):
    """Generate HTML for one chapter/overture page.
    all_nums: ordered list of all chapter numbers (may include 0 for overture).
    Navigation prev/next is computed by position in all_nums.
    """
    slug  = slugify(num)
    idx   = all_nums.index(num)
    prev_num = all_nums[idx - 1] if idx > 0 else None
    next_num = all_nums[idx + 1] if idx + 1 < len(all_nums) else None

    prev_link = (f'<a href="{slugify(prev_num)}.html">← {chapter_nav_label(prev_num)}</a>'
                 if prev_num is not None else '')
    next_link = (f'<a href="{slugify(next_num)}.html">{chapter_nav_label(next_num)} →</a>'
                 if next_num is not None else '')

    title, subtitle, rest = extract_heading(body)
    paragraphs = text_to_paragraphs(rest)
    edit_url = f"{PAGES_URL}/edits/{slug}.json"
    api_url  = f"https://api.github.com/repos/{REPO}/contents/edits/{slug}.json"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{chapter_label(num)} — {html.escape(title)} | {BOOK_TITLE}</title>
<meta name="chapter" content="{num}">
<meta name="total-chapters" content="{len([n for n in all_nums if n > 0])}">
<meta name="edit-endpoint" content="{api_url}">
<meta name="edit-retrieve" content="{edit_url}">
<style>{CSS}</style>
</head>
<body>
<header>
  <div class="book-title">{html.escape(BOOK_TITLE)} · {html.escape(AUTHOR)}</div>
  <h1><a href="../index.html" style="text-decoration:none;color:inherit">{BOOK_TITLE}</a></h1>
  <nav>
    <a href="../index.html">All Chapters</a>
    {prev_link}
    {next_link}
    <a href="../llm-interface.html">LLM Guide</a>
  </nav>
</header>

<div class="edit-bar">
  📝 <strong>LLM Edit API:</strong>
  Read edit: <a href="{edit_url}">{edit_url}</a> ·
  Save edit: <code>PUT {api_url}</code> (requires API key)
</div>

<article>
  <div class="chapter-number">{chapter_label(num)}</div>
  <div class="chapter-heading">{html.escape(title)}</div>
  {'<div class="chapter-subheading">' + html.escape(subtitle) + '</div>' if subtitle else ''}
  <div class="chapter-text">
{paragraphs}
  </div>
</article>

<footer>
  <span>{BOOK_TITLE} — {AUTHOR}</span>
  <span>Built {build_date} · <a href="../index.html">Index</a></span>
</footer>
</body>
</html>"""

def make_index_html(chapters_meta, build_date):
    """chapters_meta: list of (num, title, subtitle, word_count).
    num==0 is the Overture and renders before Chapter 1.
    """
    rows = ""
    for num, title, subtitle, word_count in chapters_meta:
        slug = slugify(num)
        label = "Overture" if num == 0 else f"Ch {num}"
        rows += f"""  <li>
    <span class="ch-num">{label}</span>
    <a href="chapters/{slug}.html">{html.escape(title)}</a>
    {'<span class="meta">' + html.escape(subtitle) + '</span>' if subtitle else ''}
    <span class="meta">{word_count:,} words</span>
  </li>\n"""

    total_words = sum(wc for _, _, _, wc in chapters_meta)
    num_chapters = len([n for n, _, _, _ in chapters_meta if n > 0])
    has_overture = any(n == 0 for n, _, _, _ in chapters_meta)
    chapter_desc = f"{num_chapters} chapters" + (" + Overture" if has_overture else "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{BOOK_TITLE} — Chapter Index</title>
<meta name="llm-interface" content="{PAGES_URL}/llm-interface.html">
<meta name="total-chapters" content="{num_chapters}">
<meta name="total-words" content="{total_words}">
<style>{CSS}</style>
</head>
<body>
<header>
  <div class="book-title">Manuscript · {AUTHOR}</div>
  <h1>{BOOK_TITLE}</h1>
  <p class="meta" style="margin-top:0.4rem">
    {chapter_desc} · {total_words:,} words ·
    <a href="llm-interface.html">LLM Interface Guide</a>
  </p>
</header>

<ul class="chapter-list">
{rows}</ul>

<footer>
  <span>Built {build_date}</span>
  <span><a href="llm-interface.html">LLM Guide</a> · <a href="https://github.com/{REPO}">GitHub</a></span>
</footer>
</body>
</html>"""

def make_llm_interface_html(chapters_meta, build_date):
    chapter_rows = "\n".join(
        f'  <tr><td>{"Overture" if num == 0 else num}</td>'
        f'<td><a href="{PAGES_URL}/chapters/{slugify(num)}.html">'
        f'{PAGES_URL}/chapters/{slugify(num)}.html</a></td>'
        f'<td>{html.escape(title)}</td></tr>'
        for num, title, _, _ in chapters_meta
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LLM Interface Guide — {BOOK_TITLE}</title>
<style>
{CSS}
code {{ background:#f4f4f0; padding:0.1em 0.4em; border-radius:3px; font-size:0.9em; }}
pre {{ background:#f4f4f0; padding:1rem; border-radius:6px; overflow-x:auto; margin:1em 0; font-size:0.85rem; line-height:1.6; }}
table {{ width:100%; border-collapse:collapse; margin:1em 0; font-size:0.9rem; }}
th {{ text-align:left; border-bottom:2px solid #ddd; padding:0.4rem 0.6rem; }}
td {{ border-bottom:1px solid #eee; padding:0.4rem 0.6rem; vertical-align:top; }}
h2 {{ font-size:1.2rem; font-weight:normal; margin:2rem 0 0.5rem; }}
</style>
</head>
<body>
<header>
  <div class="book-title">{BOOK_TITLE} · LLM Interface</div>
  <h1>LLM Access Guide</h1>
  <nav><a href="index.html">Chapter Index</a></nav>
</header>

<h2>Reading Chapters</h2>
<p>Fetch any chapter as plain HTML. No auth required.</p>
<pre>GET {PAGES_URL}/index.html                   # master chapter list
GET {PAGES_URL}/chapters/overture.html         # overture / prologue
GET {PAGES_URL}/chapters/chapter-01.html       # chapter 1
GET {PAGES_URL}/chapters/chapter-NN.html       # any chapter (01–19)</pre>

<h2>Saving an Edited Chapter</h2>
<p>PUT to the GitHub Contents API with your API key. The edit is stored as a JSON file and retrievable via a stable URL.</p>
<pre>PUT https://api.github.com/repos/{REPO}/contents/edits/chapter-01.json

Headers:
  Authorization: token &lt;API_KEY&gt;
  Content-Type: application/json

Body:
{{
  "message": "LLM edit — chapter 1",
  "content": "&lt;base64-encoded JSON&gt;",
  "sha": "&lt;current file SHA if updating, omit if new&gt;"
}}

Edit payload (base64 encode this):
{{
  "chapter": 1,
  "edited_at": "ISO-8601 timestamp",
  "agent": "your agent name",
  "text": "full edited chapter text here"
}}</pre>

<h2>Retrieving a Saved Edit</h2>
<pre>GET {PAGES_URL}/edits/chapter-01.json    # direct URL, no auth
GET {PAGES_URL}/edits/overture.json      # overture edit</pre>

<h2>Checking if an Edit Exists</h2>
<pre>GET https://api.github.com/repos/{REPO}/contents/edits/chapter-01.json
# Returns 404 if no edit saved yet, 200 with content + sha if it exists</pre>

<h2>Chapter Directory</h2>
<table>
  <tr><th>#</th><th>URL</th><th>Title</th></tr>
{chapter_rows}
</table>

<footer>
  <span>Built {build_date}</span>
  <span><a href="https://github.com/{REPO}">GitHub Repo</a></span>
</footer>
</body>
</html>"""

def build(txt_path=None):
    txt = Path(txt_path) if txt_path else DEFAULT_TXT
    if not txt.exists():
        # Find newest txt in Manuscript Masters
        txts = sorted(GDRIVE.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not txts:
            print(f"ERROR: No TXT file found in {GDRIVE}")
            sys.exit(1)
        txt = txts[0]
    print(f"Parsing: {txt}")

    CHAPTER_DIR.mkdir(exist_ok=True)
    EDITS_DIR.mkdir(exist_ok=True)

    chapters = parse_chapters(txt)
    all_nums = [num for num, _ in chapters]   # ordered list incl. 0 for overture
    date     = datetime.now().strftime("%Y-%m-%d")
    print(f"Found {len(chapters)} sections ({sum(1 for n in all_nums if n > 0)} chapters"
          + (", 1 overture" if 0 in all_nums else "") + ")")

    chapters_meta = []
    for num, body in chapters:
        title, subtitle, rest = extract_heading(body)
        word_count = len(body.split())
        chapters_meta.append((num, title, subtitle, word_count))
        out = CHAPTER_DIR / f"{slugify(num)}.html"
        out.write_text(make_chapter_html(num, body, all_nums, date), encoding='utf-8')
        label = "Overture" if num == 0 else f"Chapter {num:2d}"
        print(f"  ✓ {label}: {title[:50]}")

    (OUT_DIR / "index.html").write_text(make_index_html(chapters_meta, date), encoding='utf-8')
    (OUT_DIR / "llm-interface.html").write_text(make_llm_interface_html(chapters_meta, date), encoding='utf-8')

    # Placeholder for edits dir
    (EDITS_DIR / ".gitkeep").touch()

    print(f"\nDone — {len(chapters)} sections written to {OUT_DIR}")
    print(f"Live at: {PAGES_URL}")

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
