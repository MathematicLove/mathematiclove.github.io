#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "downloads")
ROOT = os.path.abspath(ROOT)
MANIFEST = "_manifest.json"
# Files of the listing page itself (only at the top level of downloads/).
SERVICE = {"index.html", MANIFEST}

def git_dates(path):
    """(added, modified) commit dates of a file; checkout mtimes are
    meaningless in CI. Falls back to filesystem mtime for uncommitted files."""
    try:
        out = subprocess.run(
            ["git", "log", "--follow", "--format=%cI", "--", path],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.split()
        if out:
            return out[-1], out[0]
    except (OSError, subprocess.CalledProcessError):
        pass
    ts = os.path.getmtime(path)
    iso = datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")
    return iso, iso


def walk(abs_dir, rel_dir):
    items = []
    for name in sorted(os.listdir(abs_dir), key=str.lower):
        if name.startswith("."):
            continue
        if rel_dir == "" and name in SERVICE:
            continue
        abs_path = os.path.join(abs_dir, name)
        rel_path = f"{rel_dir}{name}"
        if os.path.isdir(abs_path):
            children = walk(abs_path, rel_path + "/")
            items.append({
                "type": "dir",
                "name": name,
                "path": rel_path + "/",
                "children": children,
            })
        elif os.path.isfile(abs_path):
            added, modified = git_dates(abs_path)
            items.append({
                "type": "file",
                "name": name,
                "path": rel_path,
                "size": os.path.getsize(abs_path),
                "added": added,
                "mtime": modified,
            })
    # Folders first, then files
    items.sort(key=lambda i: (i["type"] != "dir", i["name"].lower()))
    return items

def main():
    if not os.path.isdir(ROOT):
        print(f"no {ROOT}, nothing to do")
        return 0
    tree = walk(ROOT, "")
    data = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": tree,
    }
    with open(os.path.join(ROOT, MANIFEST), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    def count(items):
        return sum(count(i["children"]) if i["type"] == "dir" else 1 for i in items)

    print(f"manifest: {count(tree)} files")
    return 0

def serve(port=8000):
    """Local preview: serves the site and rebuilds the manifest on every page load."""
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0].endswith("/downloads/" + MANIFEST):
                main()
            super().do_GET()

    site = os.path.dirname(ROOT)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=site))
    print(f"http://localhost:{port}/downloads/  (Ctrl+C to stop)")
    httpd.serve_forever()


if __name__ == "__main__":
    if "--serve" in sys.argv:
        serve()
    else:
        sys.exit(main())