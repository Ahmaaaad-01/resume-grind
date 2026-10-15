"""Inspect a reference or generated resume PDF without changing it."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pdfplumber


def inspect(path: Path) -> dict:
    pages = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, 1):
            chars = [c for c in page.chars if c.get("text", "").strip()]
            grouped = {}
            for char in chars:
                key = round(char["top"] / 2) * 2
                grouped.setdefault(key, []).append(char)
            lines = []
            for top, row in sorted(grouped.items()):
                row.sort(key=lambda c: c["x0"])
                lines.append({
                    "top": round(min(c["top"] for c in row), 2),
                    "bottom": round(max(c["bottom"] for c in row), 2),
                    "x0": round(min(c["x0"] for c in row), 2),
                    "x1": round(max(c["x1"] for c in row), 2),
                    "text": "".join(c["text"] for c in row),
                })
            pages.append({
                "page": number,
                "width_pt": page.width,
                "height_pt": page.height,
                "text": page.extract_text(x_tolerance=2, y_tolerance=3),
                "fonts": [{"font": font, "size": size, "characters": count}
                          for (font, size), count in Counter(
                              (c["fontname"], round(c["size"], 2)) for c in chars
                          ).most_common()],
                "content_bounds": None if not chars else {
                    "left": min(c["x0"] for c in chars),
                    "right": max(c["x1"] for c in chars),
                    "top": min(c["top"] for c in chars),
                    "bottom": max(c["bottom"] for c in chars),
                },
                "lines": lines,
                "bullet_line_counts": bullet_line_counts(page),
            })
    return {"source": str(path.resolve()), "page_count": len(pages), "pages": pages}


def bullet_line_counts(page):
    counts = []
    previous_top = None
    active = False
    for line in page.extract_text_lines(x_tolerance=2, y_tolerance=3):
        if line["text"].lstrip().startswith("\u2022"):
            counts.append(1)
            active = True
        elif active and 53 <= line["x0"] <= 55 and previous_top is not None and line["top"] - previous_top < 16:
            counts[-1] += 1
        else:
            active = False
        previous_top = line["top"]
    return counts


def check_resume(report, planned_layout=None):
    errors = []
    warnings = []
    if report["page_count"] != 1:
        errors.append(f"Expected one page; found {report['page_count']}")
    for page in report["pages"]:
        if abs(page["width_pt"] - 612) > 0.5 or abs(page["height_pt"] - 792) > 0.5:
            errors.append("Page size differs from US Letter")
        bounds = page["content_bounds"]
        if not bounds:
            errors.append("Page has no text")
            continue
        if bounds["left"] < 35.5 or bounds["right"] > 576.5:
            errors.append("Text exceeds the reference's horizontal bounds")
        if bounds["top"] < 18 or bounds["bottom"] > 742:
            errors.append("Text exceeds the allowed vertical bounds")
        if bounds["bottom"] < 715:
            warnings.append("Page is less dense than the reference; review relevance and spacing")
        for item in page["fonts"]:
            if "TimesNewRoman" not in item["font"] and "Arial" not in item["font"]:
                errors.append(f"Unexpected or substituted font: {item['font']}")
            if abs(item["size"] - 12) > 0.05 and abs(item["size"] - 20) > 0.05:
                errors.append(f"Unexpected font size: {item['size']}")
    if planned_layout and report["page_count"] == 1:
        plan = json.loads(Path(planned_layout).read_text(encoding="utf-8"))
        expected = [b["line_count"] for b in plan["bullets"]] + [1, 1]
        actual = report["pages"][0]["bullet_line_counts"]
        if expected != actual:
            errors.append(f"Rendered bullet lines differ from the plan: expected {expected}, actual {actual}")
        for header in plan.get("header_rows", []):
            # Remove whitespace because the character-based report omits gaps
            # between the two independently aligned header values.
            compact = lambda text: "".join(text.split())
            wanted = compact(header["left"] + header["right"])
            matches = [line for line in report["pages"][0]["lines"] if compact(line["text"]) == wanted]
            if len(matches) != 1:
                errors.append(f"Header values must share one line: {header['left']} / {header['right']}")
            elif abs(matches[0]["x1"] - header["right_edge_pt"]) > 0.5:
                errors.append(f"Header does not end at the right margin: {header['right']}")
    return {"passed": not errors, "errors": errors, "warnings": warnings,
            "visual_review_required": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--check-resume", action="store_true")
    parser.add_argument("--planned-layout", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = inspect(args.pdf)
    if args.check_resume:
        report["checks"] = check_resume(report, args.planned_layout)
    (args.output_dir / "layout.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.output_dir / "text.txt").write_text("\n\n".join(p["text"] or "" for p in report["pages"]), encoding="utf-8")
    if args.render:
        with pdfplumber.open(args.pdf) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                page.to_image(resolution=144).save(args.output_dir / f"page-{i}.png")
    for page in report["pages"]:
        print(json.dumps({k: page[k] for k in ("page", "width_pt", "height_pt", "fonts", "content_bounds")}, indent=2))
    print(f"Pages: {report['page_count']}")
    if args.check_resume:
        print(json.dumps(report["checks"], indent=2))
        if not report["checks"]["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
