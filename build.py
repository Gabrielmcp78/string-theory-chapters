#!/usr/bin/env python3
"""
build.py — String Theory Chapter Site Builder (DOCX Edition)
Source: DOCX export from Pages (preserves bold, italic, paragraph styles)

Outputs per chapter:
  chapters/chapter-NN.html   — styled reader page
  chapters/chapter-NN.txt    — plain text (parser/LLM-friendly, no HTML)
  manifest.json              — full site index with chapter metadata + scene spans
  String Theory.epub         — EPUB 2 for reading apps
"""

import re, sys, html, zipfile, json
from pathlib import Path
from datetime import datetime
import docx

# -- Config -------------------------------------------------------------------
GDRIVE      = Path.home() / "Library/CloudStorage/GoogleDrive-gabemcpherson@gmail.com/My Drive/Manuscript Masters"
DEFAULT_SRC = GDRIVE / "String Theory - Draft 6.6.docx"
OUT_DIR     = Path(__file__).parent
CHAPTER_DIR = OUT_DIR / "chapters"
EDITS_DIR   = OUT_DIR / "edits"
REPO        = "Gabrielmcp78/string-theory-chapters"
PAGES_URL   = "https://gabrielmcp78.github.io/string-theory-chapters"
BOOK_TITLE  = "String Theory"
AUTHOR      = "Gabriel McPherson"

CHAPTER_RE = re.compile(r'^\s*\|\s*(\d+|Overture|Prologue)\s*\|\s*$', re.IGNORECASE)

STYLE_CLASS = {
    'Body':            'body',
    'Default':         'default',
    'Scene':           'scene',
    'SubChapter':      'subchapter',
    'Tempo Marking 1': 'tempo-1',
    'Tempo Marking 2': 'tempo-2',
    'location':        'location',
    'Chapter':         'ch-special',
    'Chapter Title':   'ch-title-alt',
    'Equations':       'equation',
    'Caption':         'caption',
    'Dedication':      'dedication',
    'Body 3':          'body3',
    'Subtitle':        'subtitle',
    'Title':           'title-special',
}

# Cover palette:
#   Charcoal slate:  #2b3540
#   Copper accent:   #b8785a
#   Body bg (cream): #fafaf8

# -- CSS ----------------------------------------------------------------------
CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

/* ===== Page shell ===== */
body {
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 1.1rem;
    line-height: 1.85;
    color: #1a1a1a;
    background: #fafaf8;
    max-width: 720px;
    margin: 0 auto;
    padding: 0 0 4rem;
}

/* ===== Site header — cover palette: dark slate + copper ===== */
header {
    background: #2b3540;
    padding: 1.4rem 1.5rem 1.2rem;
    margin-bottom: 2.8rem;
    border-bottom: 2px solid #b8785a;
}
header .book-title {
    font-size: 0.78rem; color: #b8785a;
    letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 0.35rem;
}
h1 {
    font-size: 1.5rem; font-weight: normal; margin: 0.2rem 0 0.5rem;
    color: #f0ece4; letter-spacing: 0.01em;
}
nav { font-size: 0.88rem; margin-top: 0; }
nav a { color: #9baab8; text-decoration: none; margin-right: 1.3rem; }
nav a:hover { color: #d4a882; text-decoration: none; }

/* ===== Chapter identity block ===== */
.article-inner { padding: 0 1.5rem; }
.book-label {
    font-size: 0.78rem; color: #b8785a; letter-spacing: 0.13em;
    text-transform: uppercase; margin-bottom: 0.45rem;
}
.chapter-number {
    font-size: 0.95rem; color: #b8785a; letter-spacing: 0.14em;
    text-transform: uppercase; margin-bottom: 0.45rem; font-weight: 500;
}
.chapter-heading {
    font-size: 2.0rem; font-weight: normal; margin-bottom: 0.55rem;
    line-height: 1.25; color: #1a1a1a;
}
.chapter-subheading {
    font-size: 1.05rem; color: #555; font-style: italic; margin-bottom: 2.2rem;
}

/* ===== Body styles from DOCX ===== */
p.body, p.default, p.body3 { margin-bottom: 1.1em; }
p.scene   { font-style: italic; color: #555; margin-bottom: 1em; }
p.dedication { font-style: italic; color: #555; margin-bottom: 0.8em; }

/* ===== Musical / structural styles ===== */
.location {
    font-size: 0.8rem; letter-spacing: 0.1em; text-transform: uppercase;
    color: #b8785a; margin: 2.2em 0 0.3em; white-space: pre-wrap;
    font-weight: 500;
}
.tempo-1 {
    font-style: italic; font-size: 0.88rem; color: #777;
    margin: 0 0 1em; line-height: 1.5;
}
.tempo-2 {
    font-style: italic; font-size: 0.98rem; color: #555;
    margin: 0.2em 0 1.4em;
}
h3.subchapter {
    font-size: 1.05rem; font-weight: normal; color: #333;
    margin: 2.4em 0 0.4em; letter-spacing: 0.01em;
}
.ch-special {
    font-variant: small-caps; letter-spacing: 0.07em;
    color: #555; margin: 0.8em 0; font-size: 0.95rem;
}
.ch-title-alt {
    font-style: italic; color: #555; font-size: 0.95rem;
    margin: 0.4em 0 1em;
}
.equation {
    font-style: italic; text-align: center; color: #333;
    margin: 1.2em auto; font-size: 0.95rem;
}
.caption {
    font-size: 0.82rem; color: #999; text-align: center;
    letter-spacing: 0.06em; margin: 0.6em 0;
}
.title-special {
    font-variant: small-caps; font-size: 1.1rem;
    letter-spacing: 0.1em; margin: 1em 0 0.5em;
}
.subtitle { display: none; }

/* ===== Verification stats bar ===== */
.chapter-stats {
    background: #f0ede8; border: 1px solid #ddd;
    border-left: 3px solid #b8785a;
    border-radius: 0 6px 6px 0;
    padding: 0.9rem 1.1rem; margin-bottom: 2.5rem;
    font-size: 0.87rem; color: #666; line-height: 1.6;
}
.stats-row {
    display: flex; gap: 0.2rem 2rem; flex-wrap: wrap;
    font-variant-numeric: tabular-nums; margin-bottom: 0.65rem;
    align-items: baseline;
}
.stats-row strong { color: #2b3540; font-weight: 600; font-size: 1.0rem; }
.scene-inventory {
    border-top: 1px solid #d8d4ce; padding-top: 0.7rem;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
    gap: 0.2rem 1.5rem;
}
.scene-entry {
    display: flex; align-items: baseline;
    justify-content: space-between; gap: 0.5rem;
}
.scene-entry a {
    color: #5a4a3a; text-decoration: none; font-size: 0.83rem;
    overflow: hidden; text-overflow: ellipsis; flex: 1;
}
.scene-entry a:hover { color: #b8785a; }
.scene-range { color: #aaa; font-size: 0.77rem; white-space: nowrap; flex-shrink: 0; }

/* ===== Parser manifest (plain-text block for LLM retrieval) ===== */
.chapter-manifest {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.76rem; color: #999; line-height: 1.75;
    background: #f7f5f2; border-left: 2px solid #d4c8bc;
    padding: 0.8rem 1rem; margin-bottom: 2rem;
    white-space: pre-wrap; border-radius: 0 4px 4px 0;
}

/* ===== End-of-chapter sentinel ===== */
.chapter-sentinel {
    text-align: center; font-size: 0.78rem; color: #b8785a;
    letter-spacing: 0.15em; text-transform: uppercase;
    margin-top: 4.5rem; padding-top: 1.2rem;
    border-top: 1px solid #e0d8d0; opacity: 0.7;
}

/* ===== LLM API bar (editorial / not for readers) ===== */
.edit-bar {
    margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid #eee;
    font-size: 0.76rem; color: #bbb;
}
.edit-bar a { color: #bbb; text-decoration: none; }
.edit-bar a:hover { color: #b8785a; text-decoration: underline; }
.edit-bar code { font-size: 0.74rem; color: #ccc; }

/* ===== Footer ===== */
footer {
    margin-top: 2rem; padding: 1.2rem 1.5rem 0;
    border-top: 1px solid #ddd;
    font-size: 0.8rem; color: #aaa; display: flex; justify-content: space-between;
}
footer a { color: #aaa; }
footer a:hover { color: #b8785a; }

/* ===== Index ===== */
.chapter-list { list-style: none; }
.chapter-list li { padding: 0.65rem 0; border-bottom: 1px solid #eee; }
.chapter-list li:last-child { border-bottom: none; }
.chapter-list a { text-decoration: none; color: #1a1a1a; font-size: 1.05rem; }
.chapter-list a:hover { color: #b8785a; }
.chapter-list .ch-num { color: #b8785a; font-size: 0.82rem; min-width: 3.5rem; display: inline-block; }
.meta { font-size: 0.85rem; color: #888; margin-top: 0.3rem; }
"""

# -- Helpers ------------------------------------------------------------------
def slugify(n):
    return "overture" if n == 0 else f"chapter-{int(n):02d}"

def chapter_label(n):
    return "Overture" if n == 0 else f"Chapter {n}"

def chapter_nav_label(n):
    return "Overture" if n == 0 else f"Ch {n}"

# -- DOCX paragraph -> HTML ---------------------------------------------------
def runs_to_html(para):
    result = ''
    for run in para.runs:
        t = html.escape(run.text)
        if not t:
            continue
        if run.bold and run.italic:
            t = f'<strong><em>{t}</em></strong>'
        elif run.bold:
            t = f'<strong>{t}</strong>'
        elif run.italic:
            t = f'<em>{t}</em>'
        result += t
    return result

def para_to_html(p):
    style = p.style.name
    css_class = STYLE_CLASS.get(style, 'body')
    if css_class == 'subtitle':
        return ''
    inner = runs_to_html(p)
    inner = re.sub(r'\t+', '\u2002\u2002', inner)
    if not inner.strip():
        return ''
    if css_class in ('subchapter', 'ch-title-alt'):
        return f'<h3 class="{css_class}">{inner}</h3>\n'
    elif css_class in ('location', 'tempo-1', 'tempo-2', 'ch-special',
                       'equation', 'caption', 'title-special'):
        return f'<div class="{css_class}">{inner}</div>\n'
    else:
        return f'<p class="{css_class}">{inner}</p>\n'

def para_to_text(p):
    """Plain-text rendering for .txt companion files."""
    style = p.style.name
    css_class = STYLE_CLASS.get(style, 'body')
    if css_class == 'subtitle':
        return ''
    t = p.text.strip()
    if not t:
        return ''
    t = re.sub(r'\t+', '  ', t)
    if style == 'location':
        return f'\n{t}\n'
    elif style in ('Tempo Marking 1', 'Tempo Marking 2'):
        return f'[{t}]\n'
    elif style == 'SubChapter':
        return f'\n{t}\n'
    elif css_class in ('equation',):
        return f'  {t}\n'
    else:
        return f'{t}\n'

# -- DOCX parser --------------------------------------------------------------
def parse_chapters(src_path):
    doc = docx.Document(str(src_path))
    paras = doc.paragraphs
    markers = []
    for i, p in enumerate(paras):
        m = CHAPTER_RE.match(p.text.strip())
        if m:
            raw = m.group(1)
            num = 0 if raw.lower() in ('overture', 'prologue') else int(raw)
            markers.append((i, num))
    chapters = []
    for j, (start_idx, num) in enumerate(markers):
        end_idx = markers[j+1][0] if j + 1 < len(markers) else len(paras)
        chapters.append((num, paras[start_idx + 1:end_idx]))
    return chapters

def extract_meta(paras):
    title = subtitle = ''
    for p in paras:
        t = p.text.strip()
        if not t:
            continue
        if p.style.name == 'SubChapter' and not title:
            title = t
        elif p.style.name in ('Tempo Marking 2', 'Chapter Title') and not subtitle:
            subtitle = t
        if title and subtitle:
            break
    if not title:
        for p in paras:
            if p.text.strip():
                title = p.text.strip()
                break
    word_count = sum(len(p.text.split()) for p in paras)
    return title, subtitle, word_count

def strip_header_paras(paras):
    """Skip the opening SubChapter + Tempo Marking 2 already in the article header."""
    idx = 0
    while idx < len(paras) and not paras[idx].text.strip():
        idx += 1
    if idx < len(paras) and paras[idx].style.name == 'SubChapter':
        idx += 1
        while idx < len(paras) and not paras[idx].text.strip():
            idx += 1
        if idx < len(paras) and paras[idx].style.name == 'Tempo Marking 2':
            idx += 1
    return paras[idx:]

def render_body_html(paras):
    """Render body HTML with scene anchors; return (html_str, stats)."""
    parts      = []
    scenes     = []
    word_count = 0
    para_count = 0

    for p in paras:
        style     = p.style.name
        css_class = STYLE_CLASS.get(style, 'body')
        if css_class == 'subtitle':
            continue
        t = p.text.strip()
        if not t:
            continue
        w           = len(p.text.split())
        word_count += w
        para_count += 1

        if style == 'location':
            if scenes:
                scenes[-1]['word_end'] = word_count - w
                scenes[-1]['para_end'] = para_count - 1
            scene_n  = len(scenes) + 1
            scene_id = f'scene-{scene_n}'
            scenes.append({
                'id':         scene_id,
                'heading':    t,
                'word_start': word_count - w + 1,
                'para_start': para_count,
                'word_end':   None,
                'para_end':   None,
            })
            inner = runs_to_html(p)
            inner = re.sub(r'\t+', '\u2002\u2002', inner)
            parts.append(f'<div class="location" id="{scene_id}">{inner}</div>\n')
        else:
            parts.append(para_to_html(p))

    if scenes:
        scenes[-1]['word_end'] = word_count
        scenes[-1]['para_end'] = para_count

    return ''.join(parts), {
        'words':      word_count,
        'paragraphs': para_count,
        'scenes':     scenes,
    }

# -- Plain-text chapter file --------------------------------------------------
def make_chapter_txt(num, title, subtitle, body_paras, stats):
    """
    Pure plain text — no HTML, no CSS.
    Fetchable at /chapters/chapter-NN.txt
    Designed to survive any HTML-to-text extraction layer intact.
    """
    label    = chapter_label(num)
    sc_list  = stats['scenes']
    sc_words = stats['words']
    sc_paras = stats['paragraphs']
    sc_count = len(sc_list)
    bar      = '=' * 72

    lines = [
        bar,
        f'{BOOK_TITLE.upper()}',
        f'By {AUTHOR}',
        bar,
        f'Chapter Label:   {label}',
        f'Title:           {title}',
    ]
    if subtitle:
        lines.append(f'Subtitle:        {subtitle}')
    lines += [
        bar,
        'CHAPTER MANIFEST',
        '-' * 40,
        f'Word Count:      {sc_words:,}',
        f'Paragraph Count: {sc_paras:,}',
        f'Scene Count:     {sc_count}',
        '',
    ]
    for i, s in enumerate(sc_list, 1):
        lines.append(
            f'Scene {i}: {s["heading"]}'
            f'  --  Words {s["word_start"]:,}\u2013{s["word_end"]:,}'
            f'  |  Paragraphs {s["para_start"]}\u2013{s["para_end"]}'
        )
    lines += [
        bar,
        '',
        '--- CHAPTER TEXT BEGINS ---',
        '',
    ]
    for p in body_paras:
        lines.append(para_to_text(p))
    lines += [
        '',
        bar,
        f'END OF {label.upper()}',
        bar,
    ]
    return '\n'.join(lines)

# -- JSON manifest ------------------------------------------------------------
def make_manifest_json(chapters_full, build_date):
    """
    Site-level manifest at /manifest.json
    chapters_full: list of (num, title, subtitle, word_count, para_count, scenes)
    """
    total_words = sum(wc for _, _, _, wc, _, _ in chapters_full)
    chapter_list = []
    for num, title, subtitle, word_count, para_count, scenes in chapters_full:
        slug = slugify(num)
        chapter_list.append({
            'num':             num,
            'slug':            slug,
            'label':           chapter_label(num),
            'title':           title,
            'subtitle':        subtitle,
            'word_count':      word_count,
            'paragraph_count': para_count,
            'scene_count':     len(scenes),
            'html_url':        f'{PAGES_URL}/chapters/{slug}.html',
            'text_url':        f'{PAGES_URL}/chapters/{slug}.txt',
            'scenes': [
                {
                    'n':          i,
                    'heading':    s['heading'],
                    'word_start': s['word_start'],
                    'word_end':   s['word_end'],
                    'para_start': s['para_start'],
                    'para_end':   s['para_end'],
                }
                for i, s in enumerate(scenes, 1)
            ],
        })
    return json.dumps({
        'title':         BOOK_TITLE,
        'author':        AUTHOR,
        'built':         build_date,
        'total_words':   total_words,
        'manifest_url':  f'{PAGES_URL}/manifest.json',
        'chapters':      chapter_list,
    }, indent=2, ensure_ascii=False)

# -- HTML page builders -------------------------------------------------------
def make_chapter_html(num, paras, all_nums, build_date,
                      prebuilt_body=None, prebuilt_stats=None):
    slug  = slugify(num)
    idx   = all_nums.index(num)
    prev_num = all_nums[idx - 1] if idx > 0 else None
    next_num = all_nums[idx + 1] if idx + 1 < len(all_nums) else None

    prev_link = (f'<a href="{slugify(prev_num)}.html">\u2190 {chapter_nav_label(prev_num)}</a>'
                 if prev_num is not None else '')
    next_link = (f'<a href="{slugify(next_num)}.html">{chapter_nav_label(next_num)} \u2192</a>'
                 if next_num is not None else '')

    title, subtitle, _ = extract_meta(paras)
    if prebuilt_body is not None and prebuilt_stats is not None:
        body_html = prebuilt_body
        stats     = prebuilt_stats
    else:
        body_paras        = strip_header_paras(paras)
        body_html, stats  = render_body_html(body_paras)

    edit_url = f"{PAGES_URL}/edits/{slug}.json"
    api_url  = f"https://api.github.com/repos/{REPO}/contents/edits/{slug}.json"
    txt_url  = f"{PAGES_URL}/chapters/{slug}.txt"

    sc_list  = stats['scenes']
    sc_count = len(sc_list)
    sc_words = stats['words']
    sc_paras = stats['paragraphs']

    # Visual stats bar
    scene_entries = ''
    for s in sc_list:
        w_range  = f'w.{s["word_start"]:,}\u2013{s["word_end"]:,}'
        p_range  = f'\u00b6{s["para_start"]}\u2013{s["para_end"]}'
        rng_span = f'<span class="scene-range">{w_range}\u00a0\u00b7\u00a0{p_range}</span>'
        scene_entries += (
            f'    <div class="scene-entry">'
            f'<a href="#{s["id"]}">{html.escape(s["heading"])}</a>'
            f'{rng_span}</div>\n'
        )
    scene_inv_html = (
        f'<div class="scene-inventory">\n{scene_entries}  </div>'
        if scene_entries else ''
    )
    stats_bar = (
        f'<div class="chapter-stats">\n'
        f'  <div class="stats-row">'
        f'<strong>{sc_words:,}</strong>&thinsp;words'
        f'&ensp;<strong>{sc_paras:,}</strong>&thinsp;paragraphs'
        f'&ensp;<strong>{sc_count}</strong>&thinsp;scene{"s" if sc_count != 1 else ""}'
        f'</div>\n  {scene_inv_html}\n</div>'
    )

    # Plain-text manifest block (in HTML content flow, for page-context extractors)
    manifest_lines = [
        f'[ Chapter Manifest: {BOOK_TITLE} \u00b7 {chapter_label(num)} ]',
        f'Title: {title}',
        f'Word Count: {sc_words:,}',
        f'Paragraph Count: {sc_paras:,}',
        f'Scene Count: {sc_count}',
    ]
    for i, s in enumerate(sc_list, 1):
        manifest_lines.append(
            f'Scene {i}: {s["heading"]}'
            f' -- Word Range: {s["word_start"]:,}\u2013{s["word_end"]:,}'
            f' | Paragraph Range: {s["para_start"]}\u2013{s["para_end"]}'
        )
    manifest_lines.append('[ End Manifest ]')
    manifest_block = (
        f'<div class="chapter-manifest">{html.escape(chr(10).join(manifest_lines))}</div>'
    )

    sentinel = (
        f'<div class="chapter-sentinel" id="chapter-end">'
        f'&#8212; End of {chapter_label(num)} &#8212;</div>'
    )

    page_title = f"{BOOK_TITLE} \u00b7 {chapter_label(num)} \u00b7 {html.escape(title)}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<meta name="book" content="{html.escape(BOOK_TITLE)}">
<meta name="chapter" content="{num}">
<meta name="word-count" content="{sc_words}">
<meta name="paragraph-count" content="{sc_paras}">
<meta name="scene-count" content="{sc_count}">
<meta name="edit-endpoint" content="{api_url}">
<meta name="edit-retrieve" content="{edit_url}">
<link rel="alternate" type="text/plain" href="{slug}.txt" title="Plain text — parser/LLM access">
<style>{CSS}</style>
</head>
<body>
<header>
  <div class="book-title">{html.escape(BOOK_TITLE)} &middot; {html.escape(AUTHOR)}</div>
  <h1><a href="../index.html" style="text-decoration:none;color:inherit">{BOOK_TITLE}</a></h1>
  <nav>
    <a href="../index.html">All Chapters</a>
    {prev_link}
    {next_link}
    <a href="{slug}.txt" style="font-size:0.8rem;color:#6a7a8a" title="Plain text version">[txt]</a>
  </nav>
</header>

<article>
  <div class="article-inner">
  <div class="book-label">{html.escape(BOOK_TITLE)} &middot; {html.escape(AUTHOR)}</div>
  <div class="chapter-number">{chapter_label(num)}</div>
  <div class="chapter-heading">{html.escape(title)}</div>
  {'<div class="chapter-subheading">' + html.escape(subtitle) + '</div>' if subtitle else ''}
  {stats_bar}
  <div class="chapter-text">
{manifest_block}
{body_html}
{sentinel}
  </div>

  <div class="edit-bar">
    LLM Edit API &mdash;
    Read: <a href="{edit_url}">{edit_url}</a> &middot;
    Save: <code>PUT {api_url}</code> &middot;
    Plain text: <a href="{txt_url}">{txt_url}</a>
  </div>
  </div>
</article>

<footer>
  <span>{BOOK_TITLE} &mdash; {AUTHOR}</span>
  <span>Built {build_date} &middot; <a href="../index.html">Index</a></span>
</footer>
</body>
</html>"""

def make_index_html(chapters_meta, build_date):
    rows = ""
    for num, title, subtitle, word_count in chapters_meta:
        slug  = slugify(num)
        label = "Overture" if num == 0 else f"Ch {num}"
        rows += f"""  <li>
    <span class="ch-num">{label}</span>
    <a href="chapters/{slug}.html">{html.escape(title)}</a>
    {'<span class="meta">' + html.escape(subtitle) + '</span>' if subtitle else ''}
    <span class="meta">{word_count:,} words</span>
  </li>\n"""

    total_words  = sum(wc for _, _, _, wc in chapters_meta)
    num_chapters = len([n for n, _, _, _ in chapters_meta if n > 0])
    has_overture = any(n == 0 for n, _, _, _ in chapters_meta)
    chapter_desc = f"{num_chapters} chapters" + (" + Overture" if has_overture else "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{BOOK_TITLE} &mdash; Chapter Index</title>
<meta name="llm-interface" content="{PAGES_URL}/llm-interface.html">
<meta name="manifest" content="{PAGES_URL}/manifest.json">
<style>{CSS}</style>
</head>
<body>
<header>
  <div class="book-title">Manuscript &middot; {AUTHOR}</div>
  <h1>{BOOK_TITLE}</h1>
  <p class="meta" style="margin-top:0.4rem">
    {chapter_desc} &middot; {total_words:,} words &middot;
    <a href="manifest.json" style="color:#b8785a">manifest.json</a>
  </p>
</header>
<ul class="chapter-list">
{rows}</ul>
<footer>
  <span>Built {build_date}</span>
  <span><a href="manifest.json">manifest.json</a> &middot; <a href="https://github.com/{REPO}">GitHub</a></span>
</footer>
</body>
</html>"""


def make_llm_interface_html(chapters_meta, build_date):
    chapter_rows = "\n".join(
        f'  <tr><td>{"Overture" if num == 0 else num}</td>'
        f'<td><a href="{PAGES_URL}/chapters/{slugify(num)}.html">'
        f'{PAGES_URL}/chapters/{slugify(num)}.html</a></td>'
        f'<td><a href="{PAGES_URL}/chapters/{slugify(num)}.txt">.txt</a></td>'
        f'<td>{html.escape(title)}</td></tr>'
        for num, title, _, _ in chapters_meta
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>LLM Interface &mdash; {BOOK_TITLE}</title>
<style>{CSS}
code{{background:#f4f4f0;padding:.1em .4em;border-radius:3px;font-size:.9em}}
pre{{background:#f4f4f0;padding:1rem;border-radius:6px;overflow-x:auto;margin:1em 0;font-size:.85rem;line-height:1.6}}
table{{width:100%;border-collapse:collapse;margin:1em 0;font-size:.9rem}}
th{{text-align:left;border-bottom:2px solid #ddd;padding:.4rem .6rem}}
td{{border-bottom:1px solid #eee;padding:.4rem .6rem;vertical-align:top}}
h2{{font-size:1.2rem;font-weight:normal;margin:2rem 0 .5rem;color:#b8785a}}
</style></head>
<body>
<header>
  <div class="book-title">{BOOK_TITLE} &middot; LLM Interface</div>
  <h1>LLM Access Guide</h1>
  <nav><a href="index.html">Chapter Index</a></nav>
</header>
<div style="padding:0 1.5rem">
<h2>Access Methods</h2>
<p style="font-size:.9rem;color:#555;margin-bottom:1rem">
  Each chapter has two access paths. The <strong>.txt URL</strong> is plain text with no HTML —
  use it when your retrieval layer may strip or flatten HTML structure.
  The manifest.json contains the full chapter inventory with scene spans.
</p>
<pre>Plain text (no HTML):  GET {PAGES_URL}/chapters/chapter-NN.txt
HTML page:             GET {PAGES_URL}/chapters/chapter-NN.html
Full site manifest:    GET {PAGES_URL}/manifest.json</pre>
<h2>Saving an Edit</h2>
<pre>PUT https://api.github.com/repos/{REPO}/contents/edits/chapter-01.json
Authorization: token &lt;API_KEY&gt;</pre>
<h2>Chapter Directory</h2>
<table><tr><th>#</th><th>HTML</th><th>TXT</th><th>Title</th></tr>
{chapter_rows}
</table>
</div>
<footer><span>Built {build_date}</span><span><a href="manifest.json">manifest.json</a> &middot; <a href="https://github.com/{REPO}">GitHub</a></span></footer>
</body></html>"""

# -- EPUB builder -------------------------------------------------------------
EPUB_CSS = """
body { font-family: Georgia, serif; font-size: 1em; line-height: 1.8;
       margin: 1em 1.5em; color: #1a1a1a; }
.book-label { font-size: 0.72em; color: #999; letter-spacing: 0.1em;
              text-transform: uppercase; margin-bottom: 0.4em; }
.chapter-number { font-size: 0.8em; color: #b8785a; letter-spacing: 0.12em;
                  text-transform: uppercase; margin-bottom: 0.25em; }
.chapter-heading { font-size: 1.5em; font-weight: normal; margin-bottom: 0.4em; }
.chapter-subheading { font-style: italic; font-size: 0.95em; color: #555;
                      margin-bottom: 1.5em; }
p.body, p.default { margin-bottom: 1em; text-indent: 0; }
p.scene { font-style: italic; color: #555; margin-bottom: 0.9em; }
.location { font-size: 0.78em; letter-spacing: 0.08em; text-transform: uppercase;
            color: #b8785a; margin: 1.8em 0 0.3em; font-weight: 500; }
.tempo-1 { font-style: italic; font-size: 0.85em; color: #777; margin-bottom: 0.8em; }
.tempo-2 { font-style: italic; font-size: 0.92em; color: #555; margin-bottom: 1.2em; }
h3.subchapter { font-size: 1em; font-weight: normal; color: #333; margin: 2em 0 0.4em; }
.ch-special { font-variant: small-caps; letter-spacing: 0.06em; color: #555;
              margin: 0.6em 0; font-size: 0.9em; }
.equation { font-style: italic; text-align: center; margin: 1em 0; }
.caption { font-size: 0.78em; color: #999; text-align: center; margin: 0.5em 0; }
.chapter-sentinel { text-align: center; font-size: 0.72em; color: #b8785a;
                    letter-spacing: 0.1em; text-transform: uppercase;
                    margin-top: 3em; padding-top: 1em; border-top: 1px solid #eee;
                    opacity: 0.6; }
"""

def make_epub(chapters_data, out_path):
    epub = zipfile.ZipFile(str(out_path), 'w')
    info = zipfile.ZipInfo('mimetype')
    info.compress_type = zipfile.ZIP_STORED
    epub.writestr(info, 'application/epub+zip')
    epub.writestr('META-INF/container.xml', (
        '<?xml version="1.0"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '  <rootfiles>\n'
        '    <rootfile full-path="OEBPS/content.opf"'
        ' media-type="application/oebps-package+xml"/>\n'
        '  </rootfiles>\n'
        '</container>'))
    epub.writestr('OEBPS/styles/main.css', EPUB_CSS)

    manifest_items, spine_items, nav_points = [], [], []
    for num, title, subtitle, body_html in chapters_data:
        slug     = slugify(num)
        label    = chapter_label(num)
        fname    = f'OEBPS/Text/{slug}.xhtml'
        sentinel = (f'<div class="chapter-sentinel">'
                    f'&#8212; End of {label} &#8212;</div>\n')
        xhtml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"'
            ' "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
            '<html xmlns="http://www.w3.org/1999/xhtml">\n'
            '<head>\n'
            f'  <title>{html.escape(BOOK_TITLE)} \u00b7 {label} \u00b7 {html.escape(title)}</title>\n'
            '  <link rel="stylesheet" type="text/css" href="../styles/main.css"/>\n'
            '</head>\n<body>\n'
            f'  <div class="book-label">{html.escape(BOOK_TITLE)} \u00b7 {html.escape(AUTHOR)}</div>\n'
            f'  <div class="chapter-number">{label}</div>\n'
            f'  <div class="chapter-heading">{html.escape(title)}</div>\n'
            + (f'  <div class="chapter-subheading">{html.escape(subtitle)}</div>\n' if subtitle else '')
            + f'  <div class="chapter-text">\n{body_html}{sentinel}  </div>\n'
            '</body>\n</html>'
        )
        epub.writestr(fname, xhtml)
        manifest_items.append(
            f'    <item id="{slug}" href="Text/{slug}.xhtml" media-type="application/xhtml+xml"/>')
        spine_items.append(f'    <itemref idref="{slug}"/>')
        nav_points.append((slug, f'{label} \u2014 {title}', f'Text/{slug}.xhtml'))

    date_str = datetime.now().strftime('%Y-%m-%d')
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="2.0">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:opf="http://www.idpf.org/2007/opf">\n'
        f'    <dc:title>{html.escape(BOOK_TITLE)}</dc:title>\n'
        f'    <dc:creator opf:role="aut">{html.escape(AUTHOR)}</dc:creator>\n'
        '    <dc:language>en</dc:language>\n'
        '    <dc:identifier id="bookid">urn:uuid:string-theory-gabriel-mcpherson</dc:identifier>\n'
        f'    <dc:date>{date_str}</dc:date>\n'
        '  </metadata>\n'
        '  <manifest>\n'
        '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>\n'
        '    <item id="css" href="styles/main.css" media-type="text/css"/>\n'
        + '\n'.join(manifest_items) + '\n'
        '  </manifest>\n'
        '  <spine toc="ncx">\n'
        + '\n'.join(spine_items) + '\n'
        '  </spine>\n'
        '</package>'
    )
    epub.writestr('OEBPS/content.opf', opf)

    nav_pts_xml = ''
    for i, (slug, label, href) in enumerate(nav_points, 1):
        nav_pts_xml += (
            f'  <navPoint id="np-{i}" playOrder="{i}">\n'
            f'    <navLabel><text>{html.escape(label)}</text></navLabel>\n'
            f'    <content src="{href}"/>\n'
            '  </navPoint>\n')
    ncx = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"'
        ' "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
        '  <head>\n'
        '    <meta name="dtb:uid" content="urn:uuid:string-theory-gabriel-mcpherson"/>\n'
        '    <meta name="dtb:depth" content="1"/>\n'
        '  </head>\n'
        f'  <docTitle><text>{html.escape(BOOK_TITLE)}</text></docTitle>\n'
        f'  <navMap>\n{nav_pts_xml}  </navMap>\n'
        '</ncx>'
    )
    epub.writestr('OEBPS/toc.ncx', ncx)
    epub.close()
    print(f"  \u2713 EPUB: {out_path.name}")

# -- Main build ---------------------------------------------------------------
def build(src_path=None):
    src = Path(src_path) if src_path else DEFAULT_SRC
    if not src.exists():
        candidates = sorted(GDRIVE.glob("*.docx"),
                            key=lambda f: f.stat().st_mtime, reverse=True)
        if not candidates:
            print(f"ERROR: No DOCX found in {GDRIVE}")
            sys.exit(1)
        src = candidates[0]
    print(f"Parsing: {src}")

    CHAPTER_DIR.mkdir(exist_ok=True)
    EDITS_DIR.mkdir(exist_ok=True)

    chapters   = parse_chapters(src)
    all_nums   = [num for num, _ in chapters]
    date       = datetime.now().strftime("%Y-%m-%d")
    num_chaps  = sum(1 for n in all_nums if n > 0)
    has_ov     = 0 in all_nums
    print(f"Found {len(chapters)} sections ({num_chaps} chapters"
          + (", 1 overture" if has_ov else "") + ")")

    chapters_meta  = []   # for index page
    chapters_full  = []   # for manifest.json
    epub_chapters  = []

    for num, paras in chapters:
        title, subtitle, word_count = extract_meta(paras)
        body_paras      = strip_header_paras(paras)
        body_html, stats = render_body_html(body_paras)

        chapters_meta.append((num, title, subtitle, word_count))
        chapters_full.append((num, title, subtitle,
                               stats['words'], stats['paragraphs'], stats['scenes']))

        # HTML chapter page
        out_html = CHAPTER_DIR / f"{slugify(num)}.html"
        out_html.write_text(
            make_chapter_html(num, paras, all_nums, date,
                              prebuilt_body=body_html, prebuilt_stats=stats),
            encoding='utf-8'
        )

        # Plain text companion (parser/LLM access)
        out_txt = CHAPTER_DIR / f"{slugify(num)}.txt"
        out_txt.write_text(
            make_chapter_txt(num, title, subtitle, body_paras, stats),
            encoding='utf-8'
        )

        lbl = "Overture" if num == 0 else f"Chapter {num:2d}"
        print(f"  \u2713 {lbl}: {title[:55]}")

        epub_chapters.append((num, title, subtitle, body_html))

    # Index + LLM guide
    (OUT_DIR / "index.html").write_text(
        make_index_html(chapters_meta, date), encoding='utf-8')
    (OUT_DIR / "llm-interface.html").write_text(
        make_llm_interface_html(chapters_meta, date), encoding='utf-8')

    # Site manifest
    (OUT_DIR / "manifest.json").write_text(
        make_manifest_json(chapters_full, date), encoding='utf-8')
    print(f"  \u2713 manifest.json")

    # EPUB
    epub_path = OUT_DIR / f"{BOOK_TITLE}.epub"
    make_epub(epub_chapters, epub_path)

    (EDITS_DIR / ".gitkeep").touch()

    print(f"\nDone \u2014 {len(chapters)} sections + EPUB + manifest written to {OUT_DIR}")
    print(f"Live at: {PAGES_URL}")
    print(f"Manifest: {PAGES_URL}/manifest.json")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
