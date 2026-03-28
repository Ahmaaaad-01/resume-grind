"""Lightweight regex-based inference for company name and job title from JD text."""

import re


def infer_company(jd_text: str) -> str:
    """Try to extract company name from JD text. Returns 'Company' if not found."""
    patterns = [
        r"(?:Company|Employer|Organization)\s*:\s*(.+?)(?:\n|$)",
        r"(?:About|Join)\s+([A-Z][A-Za-z0-9\s&'./-]{1,40}?)(?:\n|\.|\!)",
        r"([A-Z][A-Za-z0-9\s&'./-]{1,40}?)\s+is\s+(?:hiring|looking|seeking|searching)",
        r"(?:Work at|Working at)\s+([A-Z][A-Za-z0-9\s&'./-]{1,40}?)(?:\n|\.|\!)",
    ]
    for pattern in patterns:
        match = re.search(pattern, jd_text, re.MULTILINE)
        if match:
            name = match.group(1).strip().rstrip(".,!;:")
            if 2 <= len(name) <= 50:
                return name
    return "Company"


def infer_title(jd_text: str) -> str:
    """Try to extract job title from JD text. Returns 'Product Manager' if not found."""
    patterns = [
        r"(?:Job\s*Title|Position|Role)\s*:\s*(.+?)(?:\n|$)",
        r"^(.+?(?:Manager|Director|Lead|Analyst|Coordinator|Engineer|Designer|Specialist).+?)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, jd_text, re.MULTILINE | re.IGNORECASE)
        if match:
            title = match.group(1).strip().rstrip(".,!;:")
            if 3 <= len(title) <= 80:
                return title
    return "Product Manager"
