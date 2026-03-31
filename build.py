#!/usr/bin/env python3
"""
build.py — String Theory Chapter Site Builder (DOCX Edition)
─────────────────────────────────────────────────────────────
Source: DOCX export from Pages (preserves bold, italic, paragraph styles)
Splits on |  N  | / |  Overture  | markers and generates:

  /chapters/overture.html, chapter-01.html … chapter-NN.html
  /String Theory.epub
  /index.html
  /llm-interface.html
  /edits/  (LLM edit storage)

Paragraph style → HTML class mapping:
  Body          → <p class="body">
  Default       → <p class="default">  (archive fragments, headers)
  Scene         → <p class="scene">    (scene-level prose)
  SubChapter    → <h3 class="subchapter">  (section title within chapter)
  Tempo Marking 1 → <div class="tempo-1">  (musical tempo markings)
  Tempo Marking 2 → <div class="tempo-2">  (chapter subtitle / descriptor)
  location      → <div class="location">   (scene/time/place markers)
  Chapter       → <div class="ch-special"> (composer names, special labels)
  Chapter Title → <div class="ch-title-alt">
  Equations     → <div class="equation">
  Caption       → <div class="caption">
  Dedication    → <p class="dedication">
  Body 3        → <p class="body3">
"""

import re, sys, html, zipfile
from pathlib import Path
from datetime import datetime
import docx

# ── Config ────────────────────────────────────────────────────────────────────
GDRIVE      = Path.home() / "Library/CloudStorage/GoogleDrive-gabemcpherson@gmail.com/My Drive/Manuscript Masters"
DEFAULT_SRC = GDRIVE / "String Theory - Draft 6.6.docx"
OUT_DIR     = Path(__file__).parent
CHAPTER_DIR = OUT_DIR / "chapters"
EDITS_DIR   = OUT_DIR / "edits"
REPO        = "Gabrielmcp78/string-theory-chapters"
PAGES_URL   = "https://gabrielmcp78.github.io/string-theory-chapters"
BOOK_TITLE  = "String Theory"
AUTHOR      = "Gabriel McPherson"

# Matches |  N  | and |  Overture  | (Subtitle style in DOCX)
CHAPTER_RE = re.compile(r'^\s*\|\s*(\d+|Overture|Prologue)\s*\|\s*$', re.IGNORECASE)

# DOCX paragraph style → CSS class
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

# ── CSS ───────────────────────────────────────────────────────────────────────
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
header { border-bottom: 1px solid #ddd; padding-bottom: 1rem; margin-bottom: 2rem; }
header .book-title { font-size: 0.85rem; color: #888; letter-spacing: 0.08em; text-transform: uppercase; }
h1 { font-size: 1.5rem; font-weight: normal; margin: 0.3rem 0; }
nav { margin-top: 0.6rem; font-size: 0.9rem; }
nav a { color: #555; text-decoration: none; margin-right: 1.2rem; }
nav a:hover { text-decoration: underline; }

/* Book/chapter identity — read by Eleven Reader and library apps */
.book-label { font-size: 0.75rem; color: #bbb; letter-spacing: 0.12em;
              text-transform: uppercase; margin-bottom: 0.4rem; }
.chapter-number { font-size: 0.8rem; color: #aaa; letter-spacing: 0.15em;
                  text-transform: uppercase; margin-bottom: 0.3rem; }
.chapter-heading { font-size: 1.7rem; font-weight: normal; margin-bottom: 0.5rem; }
.chapter-subheading { font-size: 0.95rem; color: #666; font-style: italic; margin-bottom: 2rem; }

/* Body styles from DOCX */
p.body, p.default, p.body3 { margin-bottom: 1.1em; }
p.scene   { font-style: italic; color: #555; margin-bottom: 1em; }
p.dedication { font-style: italic; color: #555; margin-bottom: 0.8em; }

/* Structural / musical styles */
.location {
    font-size: 0.82rem; letter-spacing: 0.09em; text-transform: uppercase;
    color: #555; margin: 2em 0 0.3em; white-space: pre-wrap;
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
    margin: 2.2em 0 0.4em; letter-spacing: 0.01em;
}
.ch-special {
    font-variant: small-caps; letter-spacing: 0.07em;
    color: #444; margin: 0.8em 0; font-size: 0.95rem;
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
.subtitle { display: none; }  /* chapter markers — not rendered as content */

/* Edit bar */
.edit-bar {
    background: #f0f0ec; border: 1px solid #ddd; border-radius: 6px;
    padding: 0.8rem 1rem; margin-bottom: 2rem;
    font-size: 0.85rem; color: #555;
}
.edit-bar a { color: #2563eb; text-decoration: none; }
.edit-bar a:hover { text-decoration: underline; }

/* Footer */
footer {
    margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #eee;
    font-size: 0.8rem; color: #aaa; display: flex; justify-content: space-between;
}
footer a { color: #aaa; }

/* Index */
.chapter-list { list-style: none; }
.chapter-list li { padding: 0.6rem 0; border-bottom: 1px solid #eee; }
.chapter-list li:last-child { border-bottom: none; }
.chapter-list a { text-decoration: none; color: #1a1a1a; font-size: 1.05rem; }
.chapter-list a:hover { color: #2563eb; }
.chapter-list .ch-num { color: #aaa; font-size: 0.85rem; min-width: 3.5rem; display: inline-block; }
.meta { font-size: 0.85rem; color: #888; margin-top: 0.3rem; }
"""

# ── Helpers ───────────────────────────────────────────────────────────────────
def slugify(n):
    return "overture" if n == 0 else f"chapter-{int(n):02d}"

def chapter_label(n):
    return "Overture" if n == 0 else f"Chapter {n}"

def chapter_nav_label(n):
    return "Overture" if n == 0 else f"Ch {n}"

# ── DOCX paragraph → HTML ─────────────────────────────────────────────────────
def runs_to_html(para):
    """Convert a paragraph's runs to HTML, preserving bold and italic."""
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
    """Convert a single docx paragraph to an HTML element string."""
    style = p.style.name
    css_class = STYLE_CLASS.get(style, 'body')

    # Skip invisible / structural styles
    if css_class == 'subtitle':
        return ''

    inner = runs_to_html(p)
    # Normalise tabs used for visual alignment in location / tempo styles
    inner = re.sub(r'\t+', '\u2002\u2002', inner)   # en-space pair
    if not inner.strip():
        return ''

    if css_class in ('subchapter', 'ch-title-alt'):
        return f'<h3 class="{css_class}">{inner}</h3>\n'
    elif css_class in ('location', 'tempo-1', 'tempo-2', 'ch-special',
                       'equation', 'caption', 'title-special'):
        return f'<div class="{css_class}">{inner}</div>\n'
    else:
        return f'<p class="{css_class}">{inner}</p>\n'

# ── DOCX parser ───────────────────────────────────────────────────────────────
def parse_chapters(src_path):
    """Return list of (chapter_num, [docx_paragraphs]) from DOCX source."""
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
        chapter_paras = paras[start_idx + 1:end_idx]
        chapters.append((num, chapter_paras))
    return chapters

def extract_meta(paras):
    """Extract (title, subtitle, word_count) from a chapter's paragraph list."""
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
    """
    Remove the leading SubChapter + Tempo Marking 2 paragraphs that are
    already rendered as chapter-heading / chapter-subheading in the article
    header.  Only skips the very first SubChapter block — any SubChapter
    paragraphs that appear later in the body (section titles within a chapter)
    are left intact.

    Pattern at chapter start:
      [empty lines]
      SubChapter         <- chapter title  -> already in <div class="chapter-heading">
      [empty lines]
      Tempo Marking 2    <- subtitle       -> already in <div class="chapter-subheading">
      [empty lines]
      ... body begins here (Default/Scene instrumentation, location, etc.)
    """
    idx = 0
    # Skip leading blank paragraphs
    while idx < len(paras) and not paras[idx].text.strip():
        idx += 1
    # Skip first SubChapter (the chapter title)
    if idx < len(paras) and paras[idx].style.name == 'SubChapter':
        idx += 1
        # Skip any blank lines after the SubChapter
        while idx < len(paras) and not paras[idx].text.strip():
            idx += 1
        # Skip the immediately following Tempo Marking 2 (chapter subtitle)
        if idx < len(paras) and paras[idx].style.name == 'Tempo Marking 2':
            idx += 1
    return paras[idx:]

# ── HTML page builders ────────────────────────────────────────────────────────
def make_chapter_html(num, paras, all_nums, build_date):
    slug  = slugify(num)
    idx   = all_nums.index(num)
    prev_num = all_nums[idx - 1] if idx > 0 else None
    next_num = all_nums[idx + 1] if idx + 1 < len(all_nums) else None

    prev_link = (f'<a href="{slugify(prev_num)}.html">← {chapter_nav_label(prev_num)}</a>'
                 if prev_num is not None else '')
    next_link = (f'<a href="{slugify(next_num)}.html">{chapter_nav_label(next_num)} →</a>'
                 if next_num is not None else '')

    title, subtitle, _ = extract_meta(paras)
    body_paras = strip_header_paras(paras)
    body_html = ''.join(para_to_html(p) for p in body_paras)
    edit_url  = f"{PAGES_URL}/edits/{slug}.json"
    api_url   = f"https://api.github.com/repos/{REPO}/contents/edits/{slug}.json"

    # Title tag: book name first so library apps (Eleven Reader etc.) see it
    page_title = f"{BOOK_TITLE} · {chapter_label(num)} · {html.escape(title)}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<meta name="book" content="{html.escape(BOOK_TITLE)}">
<meta name="chapter" content="{num}">
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
  <div class="book-label">{html.escape(BOOK_TITLE)} · {html.escape(AUTHOR)}</div>
  <div class="chapter-number">{chapter_label(num)}</div>
  <div class="chapter-heading">{html.escape(title)}</div>
  {'<div class="chapter-subheading">' + html.escape(subtitle) + '</div>' if subtitle else ''}
  <div class="chapter-text">
{body_html}
  </div>
</article>

<footer>
  <span>{BOOK_TITLE} — {AUTHOR}</span>
  <span>Built {build_date} · <a href="../index.html">Index</a></span>
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
<title>{BOOK_TITLE} — Chapter Index</title>
<meta name="llm-interface" content="{PAGES_URL}/llm-interface.html">
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
<head><meta charset="UTF-8"><title>LLM Interface — {BOOK_TITLE}</title>
<style>{CSS}
code{{background:#f4f4f0;padding:.1em .4em;border-radius:3px;font-size:.9em}}
pre{{background:#f4f4f0;padding:1rem;border-radius:6px;overflow-x:auto;margin:1em 0;font-size:.85rem;line-height:1.6}}
table{{width:100%;border-collapse:collapse;margin:1em 0;font-size:.9rem}}
th{{text-align:left;border-bottom:2px solid #ddd;padding:.4rem .6rem}}
td{{border-bottom:1px solid #eee;padding:.4rem .6rem;vertical-align:top}}
h2{{font-size:1.2rem;font-weight:normal;margin:2rem 0 .5rem}}
</style></head>
<body>
<header>
  <div class="book-title">{BOOK_TITLE} · LLM Interface</div>
  <h1>LLM Access Guide</h1>
  <nav><a href="index.html">Chapter Index</a></nav>
</header>
<h2>Reading Chapters</h2>
<pre>GET {PAGES_URL}/chapters/overture.html
GET {PAGES_URL}/chapters/chapter-NN.html   (NN = 01–19)</pre>
<h2>Saving an Edit</h2>
<pre>PUT https://api.github.com/repos/{REPO}/contents/edits/chapter-01.json
Authorization: token &lt;API_KEY&gt;</pre>
<h2>Chapter Directory</h2>
<table><tr><th>#</th><th>URL</th><th>Title</th></tr>
{chapter_rows}
</table>
<footer><span>Built {build_date}</span><span><a href="https://github.com/{REPO}">GitHub</a></span></footer>
</body></html>"""

# ── EPUB builder ──────────────────────────────────────────────────────────────
EPUB_CSS = """
body { font-family: Georgia, serif; font-size: 1em; line-height: 1.8;
       margin: 1em 1.5em; color: #1a1a1a; }
.book-label { font-size: 0.7em; color: #999; letter-spacing: 0.1em;
              text-transform: uppercase; margin-bottom: 0.4em; }
.chapter-number { font-size: 0.75em; color: #999; letter-spacing: 0.12em;
                  text-transform: uppercase; margin-bottom: 0.25em; }
.chapter-heading { font-size: 1.5em; font-weight: normal; margin-bottom: 0.4em; }
.chapter-subheading { font-style: italic; font-size: 0.9em; color: #666;
                      margin-bottom: 1.5em; }
p.body, p.default { margin-bottom: 1em; text-indent: 0; }
p.scene { font-style: italic; color: #555; margin-bottom: 0.9em; }
.location { font-size: 0.78em; letter-spacing: 0.08em; text-transform: uppercase;
            color: #555; margin: 1.8em 0 0.3em; }
.tempo-1 { font-style: italic; font-size: 0.85em; color: #777; margin-bottom: 0.8em; }
.tempo-2 { font-style: italic; font-size: 0.92em; color: #555; margin-bottom: 1.2em; }
h3.subchapter { font-size: 1em; font-weight: normal; color: #333;
                margin: 2em 0 0.4em; }
.ch-special { font-variant: small-caps; letter-spacing: 0.06em; color: #444;
              margin: 0.6em 0; font-size: 0.9em; }
.equation { font-style: italic; text-align: center; margin: 1em 0; }
.caption { font-size: 0.78em; color: #999; text-align: center; margin: 0.5em 0; }
"""

def make_epub(chapters_data, out_path):
    """
    Generate an EPUB 2 file.
    chapters_data: list of (num, title, subtitle, body_html_string)
    """
    epub = zipfile.ZipFile(str(out_path), 'w')

    # mimetype must be first and uncompressed
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
        slug  = slugify(num)
        label = chapter_label(num)
        fname = f'OEBPS/Text/{slug}.xhtml'
        xhtml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"'
            ' "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
            '<html xmlns="http://www.w3.org/1999/xhtml">\n'
            '<head>\n'
            f'  <title>{html.escape(BOOK_TITLE)} · {label} · {html.escape(title)}</title>\n'
            '  <link rel="stylesheet" type="text/css" href="../styles/main.css"/>\n'
            '</head>\n<body>\n'
            f'  <div class="book-label">{html.escape(BOOK_TITLE)} · {html.escape(AUTHOR)}</div>\n'
            f'  <div class="chapter-number">{label}</div>\n'
            f'  <div class="chapter-heading">{html.escape(title)}</div>\n'
            + (f'  <div class="chapter-subheading">{html.escape(subtitle)}</div>\n' if subtitle else '')
            + f'  <div class="chapter-text">\n{body_html}  </div>\n'
            '</body>\n</html>'
        )
        epub.writestr(fname, xhtml)
        manifest_items.append(
            f'    <item id="{slug}" href="Text/{slug}.xhtml" media-type="application/xhtml+xml"/>')
        spine_items.append(f'    <itemref idref="{slug}"/>')
        nav_points.append((slug, f'{label} — {title}', f'Text/{slug}.xhtml'))

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
    print(f"  ✓ EPUB: {out_path.name}")

# ── Main build ────────────────────────────────────────────────────────────────
def build(src_path=None):
    src = Path(src_path) if src_path else DEFAULT_SRC

    # Fallback: if docx not found, try newest docx in Manuscript Masters
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

    chapters_meta  = []
    epub_chapters  = []

    for num, paras in chapters:
        title, subtitle, word_count = extract_meta(paras)
        chapters_meta.append((num, title, subtitle, word_count))

        # HTML chapter page
        out = CHAPTER_DIR / f"{slugify(num)}.html"
        out.write_text(make_chapter_html(num, paras, all_nums, date), encoding='utf-8')
        lbl = "Overture" if num == 0 else f"Chapter {num:2d}"
        print(f"  ✓ {lbl}: {title[:55]}")

        # Collect body HTML for EPUB (reuse same rendering, header paras already stripped)
        body_html = ''.join(para_to_html(p) for p in strip_header_paras(paras))
        epub_chapters.append((num, title, subtitle, body_html))

    # Index + LLM guide
    (OUT_DIR / "index.html").write_text(
        make_index_html(chapters_meta, date), encoding='utf-8')
    (OUT_DIR / "llm-interface.html").write_text(
        make_llm_interface_html(chapters_meta, date), encoding='utf-8')

    # EPUB
    epub_path = OUT_DIR / f"{BOOK_TITLE}.epub"
    make_epub(epub_chapters, epub_path)

    # Edits placeholder
    (EDITS_DIR / ".gitkeep").touch()

    print(f"\nDone — {len(chapters)} sections + EPUB written to {OUT_DIR}")
    print(f"Live at: {PAGES_URL}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
