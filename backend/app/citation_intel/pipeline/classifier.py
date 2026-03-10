"""
Classifier — assigns content_type, source_tier, tier_multiplier,
category_tier, venue_tier, and is_preprint to RawResultData.

Tier system:
  1 → top academic (.edu, .gov, flagship journals, arXiv cs.AI etc.)  multiplier 1.5
  2 → quality news, leading labs, major research orgs               multiplier 1.2
  3 → practitioner thought leaders, quality blogs/substacks          multiplier 1.0
  4 → general news, trade press                                       multiplier 0.8
  5 → unknown / unclassified                                          multiplier 0.6

Classification is deterministic — no external calls.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.citation_intel.pipeline.raw_result import RawResultData

_TIERS_PATH = Path(__file__).parent.parent / "data" / "source_tiers.json"

TIER_MULTIPLIERS: dict[int, float] = {
    1: 1.5,
    2: 1.2,
    3: 1.0,
    4: 0.8,
    5: 0.6,
}

# Venue keywords → tier
_VENUE_TIER_1 = frozenset(
    w.lower()
    for w in [
        "NeurIPS", "ICML", "ICLR", "ACL", "EMNLP", "NAACL", "CVPR", "ECCV",
        "ICCV", "AAAI", "IJCAI", "IEEE", "ACM", "Nature", "Science", "Cell",
        "The Lancet", "PNAS", "Journal of Machine Learning Research", "JMLR",
    ]
)


@lru_cache(maxsize=1)
def _load_tiers() -> dict:
    with open(_TIERS_PATH) as f:
        return json.load(f)


def _domain_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        from urllib.parse import urlparse
        return urlparse(url.lower()).netloc.lstrip("www.")
    except Exception:
        return None


def _classify_domain_tier(domain: Optional[str]) -> int:
    """Return tier 1-5 for a domain."""
    if not domain:
        return 5

    tiers = _load_tiers()

    # Tier 1: .edu, .gov suffixes
    if tiers["tier_1"].get("edu_suffix") and (domain.endswith(".edu") or ".edu." in domain):
        return 1
    if tiers["tier_1"].get("gov_suffix") and (domain.endswith(".gov") or ".gov." in domain):
        return 1
    # Tier 1 explicit domains
    for d in tiers["tier_1"]["domains"]:
        if domain == d or domain.endswith("." + d):
            return 1
    # Tier 2
    for d in tiers["tier_2"]["domains"]:
        if domain == d or domain.endswith("." + d):
            return 2
    # Tier 3
    for d in tiers["tier_3"]["domains"]:
        if domain == d or domain.endswith("." + d):
            return 3
    # Default tier 4 for any recognisable domain, tier 5 for unknown
    # Simple heuristic: if domain has a TLD we recognise, tier 4
    known_tlds = {".com", ".net", ".org", ".io", ".ai", ".co.uk", ".co"}
    if any(domain.endswith(t) for t in known_tlds):
        return 4
    return 5


def _classify_arxiv_category_tier(categories: list[str]) -> int:
    """Tier 1 = top CS/ML/physics categories; Tier 2 = everything else."""
    tiers = _load_tiers()
    tier1_cats = set(tiers["tier_1"].get("arxiv_categories_tier_1", []))
    for cat in categories:
        # Match exact or prefix (e.g. "cs.AI" matches "cs")
        if cat in tier1_cats:
            return 1
        prefix = cat.split(".")[0]
        if prefix in tier1_cats:
            return 1
    return 2


def _classify_venue_tier(venue: Optional[str]) -> Optional[int]:
    if not venue:
        return None
    venue_lower = venue.lower()
    if any(kw in venue_lower for kw in _VENUE_TIER_1):
        return 1
    return 2


def _classify_content_type(result: RawResultData) -> str:
    """
    Infer content_type from source_api and URL domain.

    - semantic_scholar → "academic"
    - arxiv → "academic"
    - perplexity → classify by domain (news / blog / academic / unknown)
    """
    if result.source_api in ("semantic_scholar", "arxiv"):
        return "academic"

    # Perplexity — classify by domain
    domain = _domain_from_url(result.url)
    if not domain:
        return "unknown"

    tiers = _load_tiers()
    # .edu / .gov → academic
    if domain.endswith(".edu") or ".edu." in domain:
        return "academic"
    if domain.endswith(".gov") or ".gov." in domain:
        return "news"  # government publication

    # Check against tier lists for type hints
    all_tier1 = tiers["tier_1"]["domains"]
    all_tier2 = tiers["tier_2"]["domains"]
    all_tier3 = tiers["tier_3"]["domains"]

    news_keywords = {"reuters", "bbc", "nytimes", "wsj", "economist", "bloomberg",
                     "guardian", "thetimes", "ft.com", "techcrunch", "theverge", "wired"}
    blog_keywords = {"simonwillison", "substack", "medium", "towardsdatascience",
                     "martinfowler", "substackcdn"}
    academic_keywords = {"arxiv", "semanticscholar", "nature", "ieee", "acm"}

    if any(kw in domain for kw in academic_keywords):
        return "academic"
    if any(kw in domain for kw in news_keywords):
        return "news"
    if any(kw in domain for kw in blog_keywords):
        return "blog"

    # Domain in tier 1 or 2 → news; tier 3 → blog
    for d in all_tier1:
        if domain == d or domain.endswith("." + d):
            return "news"
    for d in all_tier2:
        if domain == d or domain.endswith("." + d):
            return "news"
    for d in all_tier3:
        if domain == d or domain.endswith("." + d):
            return "blog"

    return "unknown"


def classify(result: RawResultData) -> RawResultData:
    """
    Classify a single RawResultData record in-place and return it.

    Sets: content_type, source_tier, tier_multiplier, category_tier,
          venue_tier, is_preprint.
    """
    # Content type
    result.content_type = _classify_content_type(result)

    # Source tier from URL
    domain = _domain_from_url(result.url)
    result.source_tier = _classify_domain_tier(domain)
    result.tier_multiplier = TIER_MULTIPLIERS[result.source_tier]

    # arXiv: category tier + mark as preprint
    if result.source_api == "arxiv" or result.arxiv_id:
        result.is_preprint = True
        result.category_tier = _classify_arxiv_category_tier(result.arxiv_categories)

    # Semantic Scholar: venue tier
    if result.source_api == "semantic_scholar":
        result.venue_tier = _classify_venue_tier(result.venue)

    return result


def classify_batch(results: list[RawResultData]) -> list[RawResultData]:
    """Classify a list of results in place."""
    for r in results:
        classify(r)
    return results
