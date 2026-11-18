"""
DataDevQuest - DDQ2026_10
Challenged By: Pablo Gomez
Level: Intermediate
Created By: Le Luu

Objective: Export a view as PNG and SVG, ask an AI to describe the PNG, and write the description into the SVG so screen readers can read it aloud. 
Then repeat it for each value of a filter: one accessible SVG per Region.
Challenge Link: https://datadevquest.com/challenges/ddq2026-10-describe-a-tableau-view-with-ai-intermediate
"""

import pandas as pd
import json
import tableauserverclient as TSC
from dotenv import load_dotenv
import os
import sys
import re
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))
PAT_NAME = os.getenv("PAT_NAME")
PAT_SECRET = os.getenv("PAT_SECRET")
SERVER_ADDRESS = os.getenv("SERVER_ADDRESS")
SITE_ID = os.getenv("SITE_ID")
IMG_DIR = os.path.join(BASE_DIR, "img")

# Get token and site id from Tableau Server/ Cloud
def get_token(PAT_NAME, PAT_SECRET, SERVER_ADDRESS, SITE_ID):
    url = SERVER_ADDRESS + "api/3.29/auth/signin"
    payload = json.dumps({
        "credentials": {
            "personalAccessTokenName": PAT_NAME,
            "personalAccessTokenSecret": PAT_SECRET,
            "site": {
                "contentUrl": SITE_ID
            }
        }
    })
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    response.raise_for_status()
    credentials = response.json()['credentials']
    return credentials['token'], credentials['site']['id']


# List workbooks from Tableau Server/ Cloud with metadata API via TSC
def list_workbook_views(PAT_NAME, PAT_SECRET, SERVER_ADDRESS, SITE_ID, workbook_name=None):
    tableau_auth = TSC.PersonalAccessTokenAuth(token_name=PAT_NAME, personal_access_token=PAT_SECRET, site_id=SITE_ID)
    server = TSC.Server(SERVER_ADDRESS, use_server_version=True)

    # Only filter by name when one is given, otherwise return every workbook on the site
    query_var = "($workbook_name: String)" if workbook_name else ""
    workbook_filter = "(filter:{name: $workbook_name})" if workbook_name else ""
    query = f"""
        query get_view_workbooks{query_var} {{
            workbooks{workbook_filter}{{
                id
                name
                views{{
                    luid
                    name
                }}
            }}
        }}
    """

    with server.auth.sign_in(tableau_auth):
        response = server.metadata.query(query, variables={"workbook_name": workbook_name})
    return response

# Parse the response from the metadata API to extract workbook information
def parse_workbooks_response(response):
    if response.get('errors'):
        raise RuntimeError(f"Metadata API error: {response['errors']}")
    workbooks = response['data']['workbooks']
    workbook_list = []
    for workbook in workbooks:
        workbook_list.append({
            "id": workbook['id'],
            "name": workbook['name'],
            "views": [{"luid": view['luid'], "name": view['name']} for view in workbook['views'] if view.get('luid')]
        })
    return workbook_list

# Append each filter value to the file name so each filtered export gets its own file,
# e.g. "Superstore_Product" + {"Region": "West"} -> "Superstore_Product_West".
def add_filter_suffix(file_name, filters):
    for value in (filters or {}).values():
        safe_value = re.sub(r'[\\/:*?"<>|\s]+', "-", str(value)).strip("-")
        if safe_value and not file_name.endswith(f"_{safe_value}"):
            file_name = f"{file_name}_{safe_value}"
    return file_name

# Download the image of a specific view from Tableau Server/ Cloud with 2 formats: PNG and SVG
# Filter is optional if filter by region is needed, e.g. {"Region": "West"}
def get_view_image(SERVER_ADDRESS, site_luid, view_id, token, file_name, img_dir, filters=None,
                   viz_width=1200, viz_height=900):

    url = f"{SERVER_ADDRESS}api/3.29/sites/{site_luid}/views/{view_id}/image"
    headers = {
        'X-Tableau-Auth': token
    }
    #docs: https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_concepts_filtering_and_sorting.htm
    #docs: https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_workbooks_and_views.htm
    filter_params = {f"vf_{field}": value for field, value in (filters or {}).items()}
    size_params = {"vizWidth": viz_width, "vizHeight": viz_height}
    os.makedirs(img_dir, exist_ok=True)
    file_name = add_filter_suffix(file_name, filters)

    saved_paths = []
    for extension, format_params in [("png", {}), ("svg", {"format": "SVG"})]:
        response = requests.get(url, headers=headers, params={**format_params, **size_params, **filter_params})
        response.raise_for_status()

        file_path = os.path.join(img_dir, f"{file_name}.{extension}")
        with open(file_path, "wb") as f:
            f.write(response.content)
        print(f"Saved image to {file_path}", file=sys.stderr)
        saved_paths.append(file_path)
    return saved_paths

# ---------------------------------------------------------------------------
# Step 3 (Ship): write the AI's alt text and summary into the SVG with code.
# Only the opening <svg> tag and the <title>/<desc> right after it are touched, so the
# rest of the drawing stays byte-for-byte identical (an AI rewriting a large Tableau SVG
# could change or cut parts of it).
# ---------------------------------------------------------------------------
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

ALT_TEXT_MAX_CHARS = 150

def add_svg_accessibility(svg_path, alt_text, summary, lang="en"):
    alt_text = " ".join(alt_text.split())
    summary = " ".join(summary.split())
    if not alt_text or not summary:
        raise ValueError("alt_text and summary must both be non-empty.")
    if len(alt_text) > ALT_TEXT_MAX_CHARS:
        raise ValueError(f"alt_text is {len(alt_text)} characters; it must be {ALT_TEXT_MAX_CHARS} or fewer.")

    with open(svg_path, encoding="utf-8") as f:
        svg = f.read()

    svg_tag = re.search(r"<svg\b[^>]*>", svg)
    if not svg_tag:
        raise ValueError(f"No <svg> tag found in {svg_path}")

    # Rebuild the opening tag: drop any earlier role/aria-labelledby/lang, then add ours
    tag = re.sub(r'\s+(role|aria-labelledby|lang)="[^"]*"', "", svg_tag.group(0))
    tag = re.sub(r"\s*/?>$", "", tag)
    new_tag = f'{tag} role="img" aria-labelledby="alt summary" lang="{escape(lang)}">'

    # Replace Tableau's placeholder <title>/<desc> (or ones written by an earlier run)
    rest = svg[svg_tag.end():]
    old_head = re.match(r"(\s*<title\b[^>]*>.*?</title>)?(\s*<desc\b[^>]*>.*?</desc>)?", rest, re.DOTALL)
    new_head = (f'\n<title id="alt">{escape(alt_text)}</title>'
                f'\n<desc id="summary">{escape(summary)}</desc>')
    new_svg = svg[:svg_tag.start()] + new_tag + new_head + rest[old_head.end():]

    # Check the result is still valid XML and says what we wrote, before saving
    root = ET.fromstring(new_svg.encode("utf-8"))
    ns = "{http://www.w3.org/2000/svg}"
    if root.find(f"{ns}title").text != alt_text or root.find(f"{ns}desc").text != summary:
        raise RuntimeError("SVG check failed: <title>/<desc> do not match the text written.")

    tmp_path = svg_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        f.write(new_svg)
    os.replace(tmp_path, svg_path)
    print(f"Added alt text and summary to {svg_path}", file=sys.stderr)
    return {"svg_path": svg_path, "alt": alt_text, "summary": summary, "lang": lang}


# ---------------------------------------------------------------------------
# Screen reader test pages: one HTML page per accessible SVG, with the SVG placed inline
# so the screen reader reads its <title> (alt text) and <desc> (summary).
# One SVG per page because every Tableau SVG reuses the same ids (clipPath1, alt, summary):
# two inline SVGs on one page would point at each other's title and clip paths.
# ---------------------------------------------------------------------------
import html
import webbrowser

TEST_PAGE_DIR = os.path.join(BASE_DIR, "accessibility_test")
SVG_NS = "{http://www.w3.org/2000/svg}"

_PAGE_STYLE = """
  body { font-family: Segoe UI, system-ui, sans-serif; margin: 0 auto; padding: 16px; max-width: 1240px;
         color: #1f2328; background: #ffffff; line-height: 1.5; }
  h1 { font-size: 1.6rem; } h2 { font-size: 1.2rem; margin-top: 2rem; }
  .how { color: #555; margin: 0 0 .5rem; }
  .frame { border: 1px solid #d0d7de; border-radius: 6px; padding: 8px; overflow-x: auto; }
  .frame svg { display: block; width: 100%; height: auto; }
  details { background: #f6f8fa; border-radius: 6px; padding: 8px 12px; }
  code { background: #f6f8fa; padding: 1px 4px; border-radius: 4px; }
  table { border-collapse: collapse; } td, th { border: 1px solid #d0d7de; padding: 6px 10px; text-align: left; }
"""

def read_svg_accessibility(svg_path):
    """Return (alt, summary, lang) from an SVG, or None if it has no alt text yet."""
    root = ET.parse(svg_path).getroot()
    title, desc = root.find(f"{SVG_NS}title"), root.find(f"{SVG_NS}desc")
    if root.get("role") != "img" or title is None or title.get("id") != "alt" or desc is None:
        return None
    return title.text or "", desc.text or "", root.get("lang", "en")

def _inline_svg_markup(svg_path):
    with open(svg_path, encoding="utf-8") as f:
        svg = f.read()
    svg = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", svg)
    # Tableau SVGs have no viewBox, so add one (copy only) to let the chart scale to the page.
    # Their width/height are in mm; drawing units are CSS pixels (96 per inch).
    tag = re.search(r"<svg\b[^>]*>", svg).group(0)
    size = re.search(r'width="([\d.]+)mm"\s+height="([\d.]+)mm"', tag)
    if size and "viewBox" not in tag:
        w, h = (round(float(v) * 96 / 25.4) for v in size.groups())
        svg = svg.replace(tag, tag.replace("<svg", f'<svg viewBox="0 0 {w} {h}"', 1), 1)
    return svg

def build_accessibility_test_pages(img_dir=IMG_DIR, out_dir=TEST_PAGE_DIR, open_browser=False):
    """Build one test page per accessible SVG in img_dir, plus index.html. Returns the index path."""
    os.makedirs(out_dir, exist_ok=True)
    rows, pages, built_pages = [], 0, set()
    for name in sorted(f for f in os.listdir(img_dir) if f.lower().endswith(".svg")):
        svg_path = os.path.join(img_dir, name)
        stem = os.path.splitext(name)[0]
        info = read_svg_accessibility(svg_path)
        if info is None:
            rows.append(f"<tr><td>{html.escape(name)}</td><td>No alt text yet: run add_svg_accessibility_text first.</td></tr>")
            continue
        alt, summary, _lang = info
        page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Screen reader test: {html.escape(stem)}</title>
<style>{_PAGE_STYLE}</style>
</head>
<body>
<p><a href="index.html">All test pages</a></p>
<h1>Screen reader test: {html.escape(stem)}</h1>
<details>
  <summary>Expected text (open after listening, to compare)</summary>
  <p><strong>Alt text ({len(alt)} characters):</strong> {html.escape(alt)}</p>
  <p><strong>Summary:</strong> {html.escape(summary)}</p>
</details>

<h2>Inline SVG</h2>
<p class="how">The SVG code is inside the page. The screen reader should read the title (alt text), then the description (summary).</p>
<div class="frame">
{_inline_svg_markup(svg_path)}
</div>
</body>
</html>
"""
        with open(os.path.join(out_dir, f"{stem}.html"), "w", encoding="utf-8") as f:
            f.write(page)
        built_pages.add(f"{stem}.html")
        pages += 1
        rows.append(f'<tr><td><a href="{html.escape(stem, quote=True)}.html">{html.escape(name)}</a></td><td>{html.escape(alt)}</td></tr>')

    index = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Screen reader test pages</title>
<style>{_PAGE_STYLE}</style>
</head>
<body>
<h1>Screen reader test pages</h1>
<p>Each page shows one chart as an inline SVG, so the screen reader reads its title (alt text) and description (summary).</p>
<table>
<thead><tr><th scope="col">SVG</th><th scope="col">Alt text</th></tr></thead>
<tbody>
{chr(10).join(rows) or '<tr><td colspan="2">No SVG files found.</td></tr>'}
</tbody>
</table>
<h2>How to test on Windows</h2>
<ul>
  <li><strong>Narrator</strong> (built in): press <kbd>Ctrl</kbd>+<kbd>Win</kbd>+<kbd>Enter</kbd> to turn it on or off. Press <kbd>H</kbd> to jump between headings and <kbd>Tab</kbd> to move between links. In scan mode, use the arrow keys to read each chart.</li>
  <li><strong>NVDA</strong> (free, nvaccess.org): press <kbd>H</kbd> for headings and <kbd>G</kbd> to jump to the next graphic.</li>
  <li>Edge and Chrome work best with both. Listen first, then open "Expected text" on each page to compare.</li>
</ul>
</body>
</html>
"""
    # Remove pages left over from SVGs that were deleted or re-exported without alt text
    for old_page in os.listdir(out_dir):
        if old_page.endswith(".html") and old_page != "index.html" and old_page not in built_pages:
            os.remove(os.path.join(out_dir, old_page))

    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index)
    print(f"Built {pages} test page(s) in {out_dir}", file=sys.stderr)
    if open_browser:
        webbrowser.open(index_path)
    return index_path
