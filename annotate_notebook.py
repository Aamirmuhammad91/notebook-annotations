import json
import requests
from pathlib import Path

API_URL = "https://service.tib.eu/sandbox/nfdi4energyannotator/annotate"

def annotate_text(text, ontology_ids=["oeo"], max_depth=0):
    """Send text to the annotation API."""
    payload = {"text": text, "ontology_ids": ontology_ids, "max_depth": max_depth}
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    resp = requests.post(API_URL, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json().get("matches", [])

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
        link_md = f"[{label}]({iri})"
        text = text[:start] + link_md + text[end:]
    return text

def annotate_notebook_file(nb_path):
    """Annotate a single .ipynb file."""
    print(f"🔍 Annotating {nb_path}")
    with open(nb_path, "r", encoding="utf-8") as f:
        notebook = json.load(f)

    changed = False
    for cell in notebook["cells"]:
        if cell["cell_type"] == "markdown":
            text = "".join(cell["source"])
            matches = annotate_text(text)
            if not matches:
                continue
            annotated_text = highlight_text_markdown(text, matches)
            cell["source"] = [annotated_text]
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
        # skip this script itself if it's a notebook version
        if "annotate_notebook" in nb.name:
            continue
        annotate_notebook_file(nb)

if __name__ == "__main__":
    main()
