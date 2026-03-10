"""
Deduplicator — identifies and collapses duplicate results across APIs.

Dedup priority order (first match wins):
  1. DOI (normalised lowercase)
  2. arXiv ID (normalised)
  3. Canonical URL (https, no UTM, no trailing slash, lowercase scheme+host)
  4. Title similarity fallback: Levenshtein ratio ≥ 0.92 (stdlib difflib)

The first-seen result is canonical. Duplicates are marked is_duplicate=True.
The canonical record's discovered_by list is extended with the duplicate's source.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.citation_intel.pipeline.raw_result import RawResultData

# UTM and tracking params to strip
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "utm_id", "fbclid", "gclid", "gad_source", "ref", "referrer",
    "s", "r", "via", "mc_cid", "mc_eid",
})

_ARXIV_ID_RE = re.compile(r"\d{4}\.\d{4,5}(v\d+)?")


def normalise_url(url: str) -> Optional[str]:
    """
    Canonical URL for dedup comparison.

    Rules:
    - Force https
    - Lowercase scheme and host
    - Strip trailing slash from path
    - Remove tracking params
    - Remove fragment (#)
    - Sort remaining query params for stability
    """
    if not url or not url.strip():
        return None
    try:
        parsed = urlparse(url.strip())
        # Force https
        scheme = "https"
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/") or "/"
        # Strip tracking params
        qs = parse_qs(parsed.query, keep_blank_values=False)
        clean_qs = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
        # Sort for stability
        query = urlencode(sorted(clean_qs.items()))
        return urlunparse((scheme, netloc, path, "", query, ""))
    except Exception:
        return None


def normalise_doi(doi: Optional[str]) -> Optional[str]:
    """Lowercase DOI, strip doi.org prefix if present."""
    if not doi:
        return None
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://doi\.org/", "", doi)
    return doi or None


def normalise_arxiv_id(arxiv_id: Optional[str]) -> Optional[str]:
    """Strip version suffix from arXiv ID (e.g. 2301.12345v2 → 2301.12345)."""
    if not arxiv_id:
        return None
    arxiv_id = arxiv_id.strip()
    match = _ARXIV_ID_RE.search(arxiv_id)
    if not match:
        return None
    # Remove version suffix
    base = re.sub(r"v\d+$", "", match.group(0))
    return base


def _title_similarity(a: Optional[str], b: Optional[str]) -> float:
    """Normalised Levenshtein ratio using stdlib difflib. 0.0 → 1.0."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def deduplicate(results: list[RawResultData]) -> list[RawResultData]:
    """
    Deduplicate a list of RawResultData in-place.

    Mutates records: sets is_duplicate and dedup_key.
    Returns the same list (with duplicates marked).

    Canonical records (first-seen on each identity) get their
    discovered_by list extended when a duplicate is found.
    """
    # Lookup tables: identity → index of canonical record in results
    seen_url: dict[str, int] = {}
    seen_doi: dict[str, int] = {}
    seen_arxiv: dict[str, int] = {}

    for i, result in enumerate(results):
        canonical_idx: Optional[int] = None

        # Build identity keys
        doi_key = normalise_doi(result.doi)
        arxiv_key = normalise_arxiv_id(result.arxiv_id)
        url_key = normalise_url(result.url) if result.url else None

        # Store dedup_key on result for DB
        result.dedup_key = doi_key or arxiv_key or url_key

        # Check DOI
        if doi_key and doi_key in seen_doi:
            canonical_idx = seen_doi[doi_key]

        # Check arXiv ID
        if canonical_idx is None and arxiv_key and arxiv_key in seen_arxiv:
            canonical_idx = seen_arxiv[arxiv_key]

        # Check URL
        if canonical_idx is None and url_key and url_key in seen_url:
            canonical_idx = seen_url[url_key]

        # Title similarity fallback (only when we have no identity match)
        if canonical_idx is None:
            for j in range(i):
                existing = results[j]
                if not existing.is_duplicate and _title_similarity(result.title, existing.title) >= 0.92:
                    canonical_idx = j
                    break

        if canonical_idx is not None:
            # This is a duplicate — mark and extend canonical's discovered_by
            result.is_duplicate = True
            canonical = results[canonical_idx]
            for api in result.discovered_by:
                if api not in canonical.discovered_by:
                    canonical.discovered_by.append(api)
            # If canonical lacks citation data and duplicate has it, copy over
            if canonical.citation_count is None and result.citation_count is not None:
                canonical.citation_count = result.citation_count
                canonical.influential_citations = result.influential_citations
        else:
            # New canonical record
            if doi_key:
                seen_doi[doi_key] = i
            if arxiv_key:
                seen_arxiv[arxiv_key] = i
            if url_key:
                seen_url[url_key] = i

    return results
