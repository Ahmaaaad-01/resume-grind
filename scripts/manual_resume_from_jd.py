import argparse
import json
import sys
from pathlib import Path

from src.config import load_config
from src.tailoring import tailor_resume
from src.doc_generator import generate_docx


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def build_job_dict(args: argparse.Namespace) -> dict:
    return {
        "title_raw": args.title,
        "company": args.company,
        "url": args.url or "manual://custom-jd",
        "location_raw": args.location or "",
        "source": "manual",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manually tailor a resume from a custom job description and generate a DOCX."
    )
    parser.add_argument("--jd-file", required=True, help="Path to a .txt file containing the job description")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--title", required=True, help="Job title")
    parser.add_argument("--location", default="", help="Job location")
    parser.add_argument("--url", default="", help="Optional job posting URL")
    parser.add_argument(
        "--resume-bank",
        default="data/master_resume/resume_bank.json",
        help="Path to resume_bank.json",
    )
    parser.add_argument(
        "--output-dir",
        default="data/resumes/manual",
        help="Directory where DOCX/JSON output should be saved",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only generate tailored JSON, skip DOCX generation",
    )
    parser.add_argument(
        "--keep-pdf",
        action="store_true",
        help="Keep the rendered PDF sidecar if PDF page-fit check runs",
    )
    parser.add_argument(
        "--skip-pdf-check",
        action="store_true",
        help="Skip PDF render/page-count check during DOCX generation",
    )
    args = parser.parse_args()

    jd_path = Path(args.jd_file)
    bank_path = Path(args.resume_bank)
    output_dir = Path(args.output_dir)

    if not jd_path.exists():
        print(f"ERROR: JD file not found: {jd_path}")
        return 1

    if not bank_path.exists():
        print(f"ERROR: Resume bank not found: {bank_path}")
        return 1

    config = load_config()
    bank = load_json(bank_path)
    jd_text = load_text(jd_path)
    job = build_job_dict(args)

    if not jd_text:
        print("ERROR: Job description file is empty.")
        return 1

    result = tailor_resume(job=job, jd_text=jd_text, bank=bank, config=config)

    tailored = result
    validation_errors = result.get("validation_errors", [])

    if not tailored:
        print("ERROR: No tailored resume returned.")
        print(json.dumps(result, indent=2))
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{args.company.replace('/', '-')}__tailored.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Saved tailored JSON to: {json_path}")

    if validation_errors:
        print("\nValidation warnings/errors:")
        for err in validation_errors:
            print(f"- {err}")

    if args.json_only:
        print("\nJSON-only mode enabled. Skipping DOCX generation.")
        return 0

    docx_path = generate_docx(
        tailored=tailored,
        bank=bank,
        job=job,
        output_dir=output_dir,
        keep_pdf=args.keep_pdf,
        skip_pdf_check=args.skip_pdf_check,
    )

    print(f"\nGenerated DOCX: {docx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())