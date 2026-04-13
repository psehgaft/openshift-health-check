#!/usr/bin/env python3
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed


def detect(name):
    path = shutil.which(name)
    return {"name": name, "found": bool(path), "path": path or ""}


def main() -> int:
    tools = sys.argv[1:] or [
        "pandoc",
        "wkhtmltopdf",
        "weasyprint",
        "prince",
        "tectonic",
        "xelatex",
        "lualatex",
        "pdflatex",
    ]

    results = {}
    with ThreadPoolExecutor(max_workers=min(len(tools), 8)) as pool:
        futures = [pool.submit(detect, tool) for tool in tools]
        for future in as_completed(futures):
            item = future.result()
            results[item["name"]] = item

    print(json.dumps(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
