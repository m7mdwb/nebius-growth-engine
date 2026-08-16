"""Render docs/one_pager.md to a PDF worth attaching to an application.

The brief asks for "roughly one page". Markdown on GitHub is fine for a reviewer who
clicks through, but the one-pager also gets attached to an email and read by someone
who will not, so it needs to exist as a document rather than as a file format.

pandoc handles the DOCX. For the PDF it would want a LaTeX engine, which is not
installed here, so this goes markdown -> HTML -> xhtml2pdf instead. That library
supports a subset of CSS, so the styling below is deliberately plain: no flexbox, no
grid, no custom properties. Points rather than rems, because it renders to paper.

    python scripts/make_onepager_pdf.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import markdown  # noqa: E402
from xhtml2pdf import pisa  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "one_pager.md"
OUT = ROOT / "docs" / "one_pager.pdf"

CSS = """
@page { size: a4; margin: 11mm 12mm 10mm 12mm; }
body  { font-family: Helvetica, Arial, sans-serif; font-size: 7.9pt;
        line-height: 1.3; color: #16171a; }
h1    { font-size: 13pt; margin: 0 0 2pt 0; color: #0b0b0b; }
h2    { font-size: 9.4pt; margin: 7pt 0 2pt 0; color: #0b0b0b;
        border-bottom: 0.6pt solid #c9c9c4; padding-bottom: 1.5pt; }
h3    { font-size: 9pt; margin: 8pt 0 2pt 0; }
p     { margin: 0 0 3.5pt 0; }
ul    { margin: 0 0 4pt 0; padding-left: 10pt; }
li    { margin: 0 0 2pt 0; }
strong{ color: #000; }
code  { font-family: Courier, monospace; font-size: 7.8pt; background: #f2f2ee; }
hr    { border: 0; border-top: 0.6pt solid #d6d6d0; margin: 6pt 0; }
em    { color: #3b3c40; }
"""


def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")

    body = markdown.markdown(
        SRC.read_text(encoding="utf-8"),
        extensions=["extra", "sane_lists"],
    )
    # xhtml2pdf renders a literal box for these, so spell them out.
    body = body.replace("—", "&#8212;").replace("×", "x").replace("→", "-&gt;")

    html = (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")

    with OUT.open("wb") as fh:
        result = pisa.CreatePDF(html, dest=fh, encoding="utf-8")

    if result.err:
        raise SystemExit(f"pdf generation reported {result.err} error(s)")

    kb = OUT.stat().st_size // 1024
    print(f"wrote {OUT.relative_to(ROOT)} ({kb} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
