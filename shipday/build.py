#!/usr/bin/env python3
"""Build index.html from familiars.json — rerun after editing the data."""
import json, pathlib, html

DATA = pathlib.Path(__file__).parent / "data" / "familiars.json"
OUT  = pathlib.Path(__file__).parent / "dist" / "index.html"
OUT.parent.mkdir(exist_ok=True)

results = json.loads(DATA.read_text())

items = "\n".join(
    f"""    <li>
      <a href="{html.escape(r['url'])}" target="_blank" rel="noopener">{html.escape(r['title'])}</a>
      <p>{html.escape(r['summary'])}</p>
    </li>"""
    for r in results
)

page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Familiars — Search Results</title>
  <style>
    body {{ font-family: Georgia, serif; max-width: 720px; margin: 3rem auto; padding: 0 1.5rem; background: #0d0d0d; color: #e8e0d0; }}
    h1   {{ font-size: 2rem; letter-spacing: .05em; border-bottom: 1px solid #444; padding-bottom: .5rem; }}
    ul   {{ list-style: none; padding: 0; }}
    li   {{ margin: 2rem 0; }}
    a    {{ font-size: 1.2rem; color: #c9a94e; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    p    {{ margin: .4rem 0 0; color: #aaa; font-size: .95rem; line-height: 1.5; }}
    footer {{ margin-top: 3rem; font-size: .8rem; color: #555; }}
  </style>
</head>
<body>
  <h1>⚔️ Familiars</h1>
  <p style="color:#666;font-size:.9rem">Top 5 results via Tavily search</p>
  <ul>
{items}
  </ul>
  <footer>Built by Claw · data: shipday/data/familiars.json</footer>
</body>
</html>"""

OUT.write_text(page)
print(f"Built → {OUT}")
