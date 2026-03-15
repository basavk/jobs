"""Parse a BLS OOH detail page into a clean Markdown document.

This module is kept as a thin compatibility shim.  Core logic now lives in
``src/jobs/parse`` so it can be imported as a proper package and tested
independently.
"""

import sys

# Re-export the public API from the package so existing callers continue to work.
from jobs.parse import clean, parse_ooh_page  # noqa: F401

if __name__ == "__main__":
    html_path = sys.argv[1] if len(sys.argv) > 1 else "electrician.html"
    result = parse_ooh_page(html_path)

    out_path = html_path.replace(".html", ".md")
    with open(out_path, "w") as f:
        f.write(result)
    print(f"Written to {out_path}")
    print()
    print(result)
