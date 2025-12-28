# pdf_sizes.py
# Requires: pip install pypdf

import os
import sys
import io
import argparse
from pathlib import Path
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from pypdf.generic import IndirectObject


PDF_PATHS = [
    r"C:\Users\fyre2\Downloads\COMP2402 Study Session - Details - Kahoot!.pdf",
    r"C:\Users\fyre2\Downloads\MATH1007 Study Session - Details - Kahoot!.pdf",
    r"C:\Users\fyre2\Downloads\MATH1104 Study Session - Details - Kahoot!.pdf",
]


def human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    u = 0
    while f >= 1024 and u < len(units) - 1:
        f /= 1024.0
        u += 1
    return f"{f:.2f} {units[u]}"


def deref(obj):
    return obj.get_object() if isinstance(obj, IndirectObject) else obj


def stream_encoded_len(stream_obj) -> int:
    """
    Returns encoded bytes for a PDF stream (best-effort):
    - Prefer /Length (encoded length in file)
    - Fall back to len(get_data()) (decoded length) if needed
    """
    s = deref(stream_obj)
    try:
        length = s.get("/Length", None)
        if length is None:
            raise KeyError
        length = deref(length)
        return int(length)
    except Exception:
        try:
            return len(s.get_data())
        except Exception:
            return 0


def iter_page_contents(page):
    contents = page.get("/Contents", None)
    if contents is None:
        return []
    contents = deref(contents)
    if isinstance(contents, list):
        return [deref(c) for c in contents]
    return [contents]


def iter_page_xobjects(page):
    res = deref(page.get("/Resources", {})) or {}
    xobj = deref(res.get("/XObject", {})) or {}
    out = []
    for _, obj in xobj.items():
        out.append(deref(obj))
    return out


def one_page_pdf_bytes(page) -> int:
    w = PdfWriter()
    w.add_page(page)
    buf = io.BytesIO()
    w.write(buf)
    return len(buf.getvalue())


def analyze_pdf(path: Path, include_standalone: bool):
    total_bytes = os.path.getsize(path)
    with open(path, "rb") as f:
        reader = PdfReader(f)
        n = len(reader.pages)

        rows = []
        for idx in range(n):
            page = reader.pages[idx]
            mb = page.mediabox
            w_pts = float(mb.width)
            h_pts = float(mb.height)

            contents_bytes = sum(stream_encoded_len(c) for c in iter_page_contents(page))
            xobj_streams = iter_page_xobjects(page)
            xobj_bytes = sum(stream_encoded_len(x) for x in xobj_streams)

            row = {
                "page": idx + 1,
                "w_pts": w_pts,
                "h_pts": h_pts,
                "contents_bytes": contents_bytes,
                "xobj_bytes": xobj_bytes,
                "xobj_count": len(xobj_streams),
            }

            if include_standalone:
                row["standalone_bytes"] = one_page_pdf_bytes(page)

            rows.append(row)

    return total_bytes, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--standalone", action="store_true",
                    help="Also write each page to a 1-page PDF in memory and report that size (slow/overcounts).")
    args = ap.parse_args()

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    pid = os.getpid()

    # De-dupe paths while preserving order
    seen = set()
    paths = []
    for p in PDF_PATHS:
        if p not in seen:
            seen.add(p)
            paths.append(p)

    for p in paths:
        path = Path(p)
        print(f"\n[{run_id} pid={pid}] === {path.name} ===", flush=True)

        if not path.exists():
            print(f"ERROR: file not found: {path}", flush=True)
            continue

        try:
            total_bytes, rows = analyze_pdf(path, args.standalone)
        except Exception as e:
            print(f"ERROR: failed to read/analyze PDF: {e}", flush=True)
            continue

        print(f"Full PDF size: {human_bytes(total_bytes)} ({total_bytes} bytes)", flush=True)
        print(f"Pages: {len(rows)}", flush=True)

        headers = ["Page", "Dims(pt)", "Contents(enc)", "XObjects(enc)", "XObj#"]
        if args.standalone:
            headers.append("1-page PDF")

        print("  " + " | ".join(f"{h:>12}" for h in headers), flush=True)
        print("  " + "-" * (15 * len(headers)), flush=True)

        for r in rows:
            dims = f'{r["w_pts"]:.0f}x{r["h_pts"]:.0f}'
            line = [
                f'{r["page"]:>12}',
                f"{dims:>12}",
                f'{human_bytes(r["contents_bytes"]):>12}',
                f'{human_bytes(r["xobj_bytes"]):>12}',
                f'{r["xobj_count"]:>12}',
            ]
            if args.standalone:
                line.append(f'{human_bytes(r["standalone_bytes"]):>12}')
            print("  " + " | ".join(line), flush=True)


if __name__ == "__main__":
    # Avoid any weird stdout buffering/duplication in some terminals
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    main()


# can you write a script that takes MATH 1104, splits it into three parts with two pages each (avoid doing anything that will cut off or mess with anything at the ends of pages. the only reason we are splitting here is to negate file size upload limits, this is why its essential you dont do anything that will damage the contents. if you have any concerns about potential issues, please tell me about them before i run your script), saves each of them to the same directory as the parent, and name them each MATH1104