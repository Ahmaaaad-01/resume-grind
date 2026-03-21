"""JD extraction with fallback chain: full page fetch → SerpAPI snippet → skip.

Returns (jd_text, jd_source, word_count) where jd_source is one of:
    'full_fetch', 'serpapi_snippet', 'skipped'
"""

import logging

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Minimum word count to consider a JD usable
MIN_WORDS_THRESHOLD = 50

# Timeout for HTTP requests (seconds)
FETCH_TIMEOUT = 15


def _count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def fetch_and_parse(url: str) -> str:
    """Fetch a URL and extract visible text using BeautifulSoup.

    Raises on network/parse errors — caller should catch.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    response = httpx.get(url, headers=headers, timeout=FETCH_TIMEOUT, follow_redirects=True)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style", "nav", "footer", "header"]):
        element.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Collapse multiple newlines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_jd(job: dict, min_words: int = MIN_WORDS_THRESHOLD) -> tuple[str, str, int]:
    """Extract job description using fallback chain.

    Args:
        job: Normalized job dict (from discovery.py) with keys:
            url, description_snippet
        min_words: Minimum word count threshold (default 50)

    Returns:
        (jd_text, jd_source, word_count) where jd_source is one of:
        'full_fetch', 'serpapi_snippet', 'skipped'
    """
    # Attempt 1: Full page fetch from apply URL
    url = job.get("url", "")
    if url:
        try:
            full_text = fetch_and_parse(url)
            word_count = _count_words(full_text)
            if word_count >= min_words:
                log.info("JD full_fetch: %d words from %s", word_count, url[:80])
                return (full_text, "full_fetch", word_count)
            else:
                log.info("JD full_fetch too short (%d words), falling back", word_count)
        except Exception:
            log.info("JD full_fetch failed for %s, falling back to snippet", url[:80])

    # Attempt 2: SerpAPI inline description
    snippet = job.get("description_snippet", "") or ""
    word_count = _count_words(snippet)
    if word_count >= min_words:
        log.info("JD serpapi_snippet: %d words", word_count)
        return (snippet, "serpapi_snippet", word_count)

    # Attempt 3: Skip — not enough content
    log.info("JD skipped: snippet only %d words (min %d)", word_count, min_words)
    return ("", "skipped", word_count)
