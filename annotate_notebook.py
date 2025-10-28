import json
import re
import requests
from pathlib import Path
from html import unescape

API_URL = "https://service.tib.eu/sandbox/nfdi4energyannotator/annotate"

def annotate_text(text, ontology_ids=["oeo"], max_depth=0):
    """Send text to the annotation API."""
    payload = {"text": text, "ontology_ids": ontology_ids, "max_depth": max_depth}
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json().get("matches", [])
    except Exception as e:
        print(f"⚠️ Annotation API error: {e}")
        return []

def merge_overlapping(matches):
    """Keep only non-overlapping longest spans."""
    filtered = []
    for m in sorted(matches, key=lambda x: (x["start"], -(x["end"] - x["start"]))):
        if all(not (m["start"] < f["end"] and m["end"] > f["start"]) for f in filtered):
            filtered.append(m)
    return filtered

def highlight_text_markdown(text, matches):
    """Insert Markdown-style links instead of HTML tags."""
    matches = merge_overlapping(matches)
    matches.sort(key=lambda m: m["start"], reverse=True)
    for m in matches:
        start, end = m["start"], m["end"]
        iri = m["iri"]
        label = text[start:end]
        # Skip if already looks like a link or contains URL syntax
        if re.search(r"https?://|www\.", label):
            continue
        text = text[:start] + f"[{label}]({iri})" + text[end:]
    return text

def clean_markdown_for_annotation(md_text):
    """Remove or mask parts that should not be annotated."""
    text = md_text

    # 1️⃣ Remove <img> tags entirely (non-visible content)
    text = re.sub(r"<img[^>]*>", "", text, flags=re.IGNORECASE)

    # 2️⃣ Mask Markdown/HTML links (so annotator ignores them)
    # Replace [text](link) and <a href="...">text</a> with just 'text'
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # markdown links
    text = re.sub(r"<a [^>]+>(.*?)</a>", r"\1", text, flags=re.IGNORECASE)

    # 3️⃣ Remove inline HTML tags like <br>, <strong>, <em>
    text = re.sub(r"</?[^>]+>", "", text)

    # 4️⃣ Unescape HTML entities
    text = unescape(text)

    return text.strip()

def annotate_notebook_file(nb_path):
    """Annotate a single .ipynb file safely."""
    print(f"🔍 Annotating {nb_path}")
    with open(nb_path, "r", encoding="utf-8") as f:
        notebook = json.load(f)

    changed = False
    for cell in notebook["cells"]:
        if cell["cell_type"] == "markdown":
            original_text = "".join(cell["source"])
            clean_text = clean_markdown_for_annotation(original_text)
            if not clean_text.strip():
                continue

            matches = annotate_text(clean_text)
            if not matches:
                continue

            annotated_visible_text = highlight_text_markdown(clean_text, matches)

            # Rebuild cell by replacing only the visible text portion
            # Keep original links and images as-is
            new_text = re.sub(
                re.escape(clean_text), annotated_visible_text, original_text, count=1
            )

            if new_text != original_text:
                cell["source"] = [new_text]
                changed = True

    if changed:
        with open(nb_path, "w", encoding="utf-8") as f:
            json.dump(notebook, f, indent=2)
        print(f"✅ Updated {nb_path}")
    else:
        print(f"⚪ No annotations for {nb_path}")

def main():
    notebooks = list(Path(".").rglob("*.ipynb"))
    print(f"📚 Found {len(notebooks)} notebooks.")
    for nb in notebooks:
        if "annotate_notebook" in nb.name:
            continue
        annotate_notebook_file(nb)

if __name__ == "__main__":
    main()
