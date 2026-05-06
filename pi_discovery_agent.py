#!/usr/bin/env python3
"""
PI Discovery Agent for PhD Applications — Arina's EU Lab Search
================================================================
Searches PubMed and the web for EU-based Principal Investigators
whose research matches Arina's profile (microglia, neuroinflammation,
AD, wet-lab confocal/IF, mouse models, single-cell RNA-seq).

Usage
-----
# Discover new PIs across all default topics:
    python pi_discovery_agent.py

# Custom query:
    python pi_discovery_agent.py --query "microglia TREM2 single-cell" --max 30

# Focus on a country:
    python pi_discovery_agent.py --query "microglia Alzheimer" --country France

# Save formatted entries to pi_database.md automatically:
    python pi_discovery_agent.py --auto-save

Requirements
------------
    pip install requests biopython

NCBI Entrez API is used (free, no key required up to 3 requests/sec).
Set NCBI_EMAIL and optionally NCBI_API_KEY in your environment to
increase rate limit to 10 requests/sec.

    export NCBI_EMAIL="arinazubair01@gmail.com"
    export NCBI_API_KEY="your_key_here"   # optional — get free at ncbi.nlm.nih.gov/account
"""

from __future__ import annotations

import os
import re
import sys
import time
import json
import argparse
import textwrap
from dataclasses import dataclass, field
from typing import Optional
from xml.etree import ElementTree as ET

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: run  pip install requests")

try:
    from Bio import Entrez
except ImportError:
    sys.exit("Missing dependency: run  pip install biopython")

# ─── Configuration ────────────────────────────────────────────────────────────

NCBI_EMAIL   = os.environ.get("NCBI_EMAIL", "arinazubair01@gmail.com")
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")

# Arina's core research keywords — used as default PubMed query building blocks
ARINA_TOPICS = [
    "microglia Alzheimer disease neuroinflammation",
    "TREM2 microglia neurodegeneration single-cell",
    "microglia innate immunity CNS NLRP3 inflammasome",
    "disease-associated microglia DAM scRNA-seq",
    "microglia immunofluorescence confocal mouse model Alzheimer",
    "microglial phagocytosis Alzheimer amyloid",
    "microglia epigenetics ATAC-seq neurodegeneration",
]

# EU country keywords used to filter PubMed affiliations
EU_COUNTRIES = [
    "Germany", "Belgium", "Netherlands", "France", "Spain",
    "Switzerland", "Denmark", "Sweden", "Norway", "Finland",
    "Austria", "Italy", "Portugal", "Poland", "Czech",
    "Luxembourg", "Ireland", "United Kingdom", "UK",
    "Scotland", "England", "Wales",
]

# Known institutions already in pi_database.md — skip these
KNOWN_INSTITUTIONS = [
    "University Medical Center – University of Freiburg",
    "LMU Munich", "DZNE Munich", "University of Luxembourg",
    "DZNE Munich", "DZNE Tübingen", "KU Leuven", "VIB",
    "DANDRITE", "UMCG", "University of Lausanne",
    "Achucarro", "University of Antwerp",
]

PI_DATABASE_PATH = os.path.join(os.path.dirname(__file__), "pi_database.md")

# ─── Data structures ──────────────────────────────────────────────────────────

@dataclass
class Paper:
    pmid: str
    title: str
    journal: str
    year: str
    doi: str
    authors: list[str]
    first_author: str
    last_author: str
    abstract: str = ""
    affiliations: list[str] = field(default_factory=list)


@dataclass
class PICandidate:
    name: str
    email: str
    institution: str
    country: str
    department: str
    papers: list[Paper] = field(default_factory=list)
    research_focus: str = ""
    techniques: list[str] = field(default_factory=list)
    relevance_score: int = 0
    notes: str = ""

    @property
    def slug(self) -> str:
        parts = self.name.lower().split()
        return parts[-1] if parts else "unknown"


# ─── PubMed search ────────────────────────────────────────────────────────────

class PubMedSearcher:
    """Wraps NCBI Entrez to search for recent papers and extract author/affiliation data."""

    def __init__(self, email: str, api_key: str = ""):
        Entrez.email   = email
        Entrez.api_key = api_key or None
        self._delay = 0.35 if not api_key else 0.11  # respect rate limits

    def search(self, query: str, max_results: int = 20,
               date_from: str = "2021", date_to: str = "2026") -> list[str]:
        """Return a list of PMIDs matching the query within the date range."""
        full_query = f"({query}) AND ({date_from}[pdat]:{date_to}[pdat])"
        handle = Entrez.esearch(db="pubmed", term=full_query,
                                retmax=max_results, sort="relevance")
        record = Entrez.read(handle)
        handle.close()
        time.sleep(self._delay)
        return record.get("IdList", [])

    def fetch_records(self, pmids: list[str]) -> list[Paper]:
        """Fetch full records for a list of PMIDs and return Paper objects."""
        if not pmids:
            return []
        handle = Entrez.efetch(db="pubmed", id=",".join(pmids),
                               rettype="xml", retmode="xml")
        raw = handle.read()
        handle.close()
        time.sleep(self._delay)
        return self._parse_xml(raw)

    @staticmethod
    def _parse_xml(xml_bytes: bytes) -> list[Paper]:
        root = ET.fromstring(xml_bytes)
        papers = []
        for article in root.findall(".//PubmedArticle"):
            try:
                papers.append(PubMedSearcher._parse_article(article))
            except Exception:
                continue
        return papers

    @staticmethod
    def _parse_article(article: ET.Element) -> Paper:
        def text(xpath: str, default: str = "") -> str:
            el = article.find(xpath)
            return "".join(el.itertext()).strip() if el is not None else default

        pmid   = text(".//PMID")
        title  = text(".//ArticleTitle")
        jrnl   = text(".//Journal/Title") or text(".//MedlineTA")
        year   = text(".//PubDate/Year") or text(".//PubDate/MedlineDate")[:4]
        doi    = ""
        for aid in article.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = aid.text or ""
                break

        authors, affiliations = [], []
        for auth in article.findall(".//Author"):
            last  = text(".//LastName", "")  # will be blank; parse directly
            _last = (auth.find("LastName") or ET.Element("x")).text or ""
            _fore = (auth.find("ForeName") or ET.Element("x")).text or ""
            full_name = f"{_fore} {_last}".strip()
            if full_name:
                authors.append(full_name)
            for aff in auth.findall("AffiliationInfo/Affiliation"):
                if aff.text:
                    affiliations.append(aff.text)

        # Also collect affiliations at article level (some records store them there)
        for aff in article.findall(".//AffiliationInfo/Affiliation"):
            if aff.text and aff.text not in affiliations:
                affiliations.append(aff.text)

        abstract_parts = []
        for ab in article.findall(".//AbstractText"):
            abstract_parts.append("".join(ab.itertext()).strip())
        abstract = " ".join(abstract_parts)

        first = authors[0] if authors else ""
        last_auth = authors[-1] if authors else ""

        return Paper(
            pmid=pmid, title=title, journal=jrnl, year=year, doi=doi,
            authors=authors, first_author=first, last_author=last_auth,
            abstract=abstract, affiliations=affiliations,
        )


# ─── Affiliation filtering ────────────────────────────────────────────────────

def is_eu_affiliation(affiliation: str) -> bool:
    """Return True if the affiliation string mentions a known EU country or city."""
    aff_lower = affiliation.lower()
    for country in EU_COUNTRIES:
        if country.lower() in aff_lower:
            return True
    # Common EU cities/institutes not caught by country name
    eu_markers = [
        "charite", "charité", "inserm", "cnrs", "mpg", "max planck",
        "helmholtz", "dzne", "vib", "fwo", "nwo", "umc", "umcg",
        "erasmus", "karolinska", "sapienza", "bologna", "lausanne",
        "zürich", "zurich", "wien", "madrid", "barcelona", "leuven",
        "ghent", "brussels", "antwerp", "groningen", "amsterdam",
        "leiden", "nijmegen", "utrecht", "heidelberg", "munich", "münchen",
        "freiburg", "tübingen", "bonn", "cologne", "berlin", "hamburg",
        "edinburgh", "oxford", "cambridge", "london", "bristol",
        "florence", "milan", "milan", "rome", "copenhagen", "oslo",
        "stockholm", "helsinki", "zurich", "bern", "geneva",
        "bordeaux", "lyon", "paris", "montpellier", "toulouse",
        "bilbao", "sevilla", "valencia", "granada",
        "lisbon", "porto", "warsaw", "prague", "budapest",
    ]
    return any(m in aff_lower for m in eu_markers)


def extract_email_from_affiliation(affiliation: str) -> Optional[str]:
    """Extract an email address from an affiliation string if present."""
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", affiliation)
    return match.group(0) if match else None


def extract_institution(affiliation: str) -> tuple[str, str]:
    """
    Returns (institution_name, country) extracted from an affiliation string.
    Very heuristic — good enough for display.
    """
    # Remove email if present
    aff = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "", affiliation).strip()
    # Split on semicolons/commas to get the most informative part
    parts = [p.strip() for p in re.split(r"[;,]", aff) if p.strip()]
    institution = parts[0] if parts else aff[:80]

    country = "Unknown"
    for c in EU_COUNTRIES:
        if c.lower() in affiliation.lower():
            country = c
            break
    return institution[:100], country


# ─── PI candidate assembly ────────────────────────────────────────────────────

def papers_to_pi_candidates(papers: list[Paper],
                             country_filter: Optional[str] = None) -> dict[str, PICandidate]:
    """
    Extract unique PI candidates (last authors with EU affiliations) from a paper list.
    Returns a dict keyed by last-author name.
    """
    candidates: dict[str, PICandidate] = {}

    for paper in papers:
        # Use last author as PI
        pi_name = paper.last_author
        if not pi_name:
            continue

        # Look for an EU affiliation linked to this author
        eu_affs = [a for a in paper.affiliations if is_eu_affiliation(a)]
        if not eu_affs:
            continue

        best_aff  = eu_affs[-1]  # last affiliation listed is usually PI's
        email     = extract_email_from_affiliation(best_aff)
        inst, cty = extract_institution(best_aff)

        if country_filter and country_filter.lower() not in cty.lower():
            continue

        # Skip if from a known institution already in db
        if any(k.lower() in inst.lower() for k in KNOWN_INSTITUTIONS):
            continue

        if pi_name not in candidates:
            candidates[pi_name] = PICandidate(
                name=pi_name,
                email=email or "— check lab website —",
                institution=inst,
                country=cty,
                department="",
            )

        candidates[pi_name].papers.append(paper)

    return candidates


def score_relevance(pi: PICandidate) -> int:
    """
    Score a PI candidate 0–5 based on keyword overlap with Arina's profile.
    Higher = more relevant.
    """
    arina_keywords = [
        "microglia", "neuroinflammation", "alzheimer", "trem2", "nlrp3",
        "inflammasome", "confocal", "immunofluorescence", "immunostaining",
        "single-cell", "scRNA-seq", "snRNA-seq", "spatial transcriptomic",
        "phagocytosis", "innate immunity", "cns", "neurodegeneration",
        "dam", "disease-associated microglia", "spp1", "iba1", "p2ry12",
        "western blot", "elisa", "mouse model", "transgenic", "app/ps1", "5xfad",
    ]
    text = " ".join(
        [p.title.lower() + " " + p.abstract.lower() for p in pi.papers]
    )
    return sum(1 for kw in arina_keywords if kw in text)


# ─── Output formatting ────────────────────────────────────────────────────────

TEMPLATE = """\
## PI-N · {name}

| Field | Value |
|-------|-------|
| **Slug** | `{slug}` |
| **Full name** | {name} |
| **Institution** | {institution} |
| **Country** | {country} |
| **Email** | {email} |
| **Website** | — check Google Scholar / lab page — |
| **Role** | — fill in — |
| **Relevance** | ★★ |

**Research focus:**
{focus}

**Key paper to cite:**
> {first_author} et al.
> "{title}"
> *{journal}* {year}. doi: {doi}
>
> *What it showed:* — summarise in 2 sentences —

**Lab wet-lab methods (exact techniques used):**
{techniques}

**Why Arina specifically fits:**
- Multi-channel IF, confocal, Fiji quantification (IGIB) match IF/imaging pipeline
- [Add 2–3 more specific overlaps from abstract keywords above]

**PhD programme:**
— Check institutional doctoral school and national funding calls —

---
"""


def format_pi_entry(pi: PICandidate) -> str:
    """Format a PICandidate as a pi_database.md block."""
    best_paper = sorted(pi.papers, key=lambda p: p.year, reverse=True)[0]
    focus_sentences = set()
    for p in pi.papers:
        for sent in re.split(r'[.!?]', p.abstract):
            if any(kw in sent.lower() for kw in ["microglia", "alzheimer", "inflam", "neurodegen"]):
                focus_sentences.add(sent.strip()[:120])
            if len(focus_sentences) >= 3:
                break
    focus_text = ". ".join(list(focus_sentences)[:3]) + "." if focus_sentences else "— see abstracts —"

    technique_keywords = [
        "confocal", "immunofluorescence", "immunostaining", "western blot", "elisa",
        "flow cytometry", "facs", "single-cell", "scrna", "spatial", "cryosection",
        "mouse model", "transgenic", "patch clamp", "atac-seq", "chip-seq",
        "phagocytosis", "lysosomal", "ipsc", "organoid",
    ]
    found = []
    text = " ".join(p.abstract.lower() for p in pi.papers)
    for kw in technique_keywords:
        if kw in text and kw not in found:
            found.append(f"- {kw.capitalize()}")
    techniques_str = "\n".join(found) if found else "- — extract from lab website —"

    return TEMPLATE.format(
        name=pi.name,
        slug=pi.slug,
        institution=pi.institution,
        country=pi.country,
        email=pi.email,
        focus=focus_text,
        first_author=best_paper.first_author,
        title=best_paper.title,
        journal=best_paper.journal,
        year=best_paper.year,
        doi=best_paper.doi or "— check PubMed —",
        techniques=techniques_str,
    )


def print_summary(candidates: dict[str, PICandidate]) -> None:
    """Print a ranked summary table to stdout."""
    ranked = sorted(candidates.values(), key=lambda c: c.relevance_score, reverse=True)
    print("\n" + "═" * 70)
    print(f"  Found {len(ranked)} EU PI candidates\n")
    print(f"  {'Rank':<5} {'Name':<30} {'Country':<14} {'Score':<6} {'Papers'}")
    print("  " + "─" * 66)
    for i, pi in enumerate(ranked, 1):
        print(f"  {i:<5} {pi.name:<30} {pi.country:<14} {pi.relevance_score:<6} {len(pi.papers)}")
    print("═" * 70 + "\n")


def print_detail(pi: PICandidate) -> None:
    """Print a detailed view for a single PI candidate."""
    print(f"\n{'─'*60}")
    print(f"  {pi.name}")
    print(f"  {pi.institution} | {pi.country}")
    print(f"  {pi.email}")
    print(f"  Score: {pi.relevance_score}/20+")
    print(f"\n  Papers ({len(pi.papers)}):")
    for p in sorted(pi.papers, key=lambda x: x.year, reverse=True)[:3]:
        print(f"    [{p.year}] {textwrap.shorten(p.title, 70)}")
        print(f"           {p.journal}  doi:{p.doi}")


# ─── Save to pi_database.md ───────────────────────────────────────────────────

def append_to_pi_database(entries: list[str], db_path: str) -> None:
    """Insert formatted PI entries before the Template section in pi_database.md."""
    with open(db_path, "r", encoding="utf-8") as f:
        content = f.read()

    marker = "## Template — Adding a New PI"
    if marker not in content:
        content += "\n\n" + "\n\n".join(entries)
    else:
        insert_block = "\n".join(entries) + "\n\n"
        content = content.replace(marker, insert_block + marker)

    with open(db_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Saved {len(entries)} new PI entries to {db_path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Discover EU PI candidates relevant to Arina's PhD application profile.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python pi_discovery_agent.py
              python pi_discovery_agent.py --query "microglia TREM2 aging" --max 40
              python pi_discovery_agent.py --country Germany --max 50
              python pi_discovery_agent.py --query "NLRP3 microglia" --auto-save
              python pi_discovery_agent.py --min-score 5 --detail --auto-save
        """),
    )
    p.add_argument("--query",      default=None,
                   help="Override default PubMed queries with a single custom query")
    p.add_argument("--country",    default=None,
                   help="Filter results to a specific country (e.g. France)")
    p.add_argument("--max",        type=int, default=25,
                   help="Max PubMed results per query (default 25)")
    p.add_argument("--min-score",  type=int, default=3,
                   help="Minimum relevance score to display (default 3)")
    p.add_argument("--detail",     action="store_true",
                   help="Print full detail for each PI above threshold")
    p.add_argument("--auto-save",  action="store_true",
                   help="Append new PI entries to pi_database.md automatically")
    p.add_argument("--dry-run",    action="store_true",
                   help="Print formatted entries but do not write to file")
    p.add_argument("--date-from",  default="2022",
                   help="Start year for PubMed date filter (default 2022)")
    p.add_argument("--date-to",    default="2026",
                   help="End year for PubMed date filter (default 2026)")
    return p


def main() -> None:
    args = build_argparser().parse_args()

    searcher = PubMedSearcher(email=NCBI_EMAIL, api_key=NCBI_API_KEY)

    queries = [args.query] if args.query else ARINA_TOPICS

    print(f"\n  PI Discovery Agent — {len(queries)} search queries | max {args.max} results each")
    print(f"  Date range: {args.date_from}–{args.date_to} | Country filter: {args.country or 'All EU'}\n")

    all_papers: list[Paper] = []
    for q in queries:
        print(f"  Searching: {q[:60]}...", end=" ", flush=True)
        pmids = searcher.search(q, max_results=args.max,
                                date_from=args.date_from, date_to=args.date_to)
        if not pmids:
            print("0 results")
            continue
        papers = searcher.fetch_records(pmids)
        all_papers.extend(papers)
        print(f"{len(papers)} papers")

    print(f"\n  Total papers fetched: {len(all_papers)}")

    # De-duplicate papers by PMID
    seen: set[str] = set()
    unique_papers = []
    for p in all_papers:
        if p.pmid not in seen:
            seen.add(p.pmid)
            unique_papers.append(p)
    print(f"  Unique papers: {len(unique_papers)}\n")

    candidates = papers_to_pi_candidates(unique_papers, country_filter=args.country)

    # Score relevance
    for pi in candidates.values():
        pi.relevance_score = score_relevance(pi)

    # Filter by minimum score
    filtered = {k: v for k, v in candidates.items() if v.relevance_score >= args.min_score}

    print_summary(filtered)

    if args.detail:
        for pi in sorted(filtered.values(), key=lambda c: c.relevance_score, reverse=True):
            print_detail(pi)

    # Format entries for pi_database.md
    ranked = sorted(filtered.values(), key=lambda c: c.relevance_score, reverse=True)
    formatted_entries = [format_pi_entry(pi) for pi in ranked]

    if args.dry_run:
        print("\n" + "─" * 60)
        print("  DRY RUN — formatted pi_database.md entries:\n")
        for entry in formatted_entries:
            print(entry)
        return

    if args.auto_save and formatted_entries:
        if not os.path.exists(PI_DATABASE_PATH):
            print(f"  Warning: {PI_DATABASE_PATH} not found — printing to stdout instead")
            for entry in formatted_entries:
                print(entry)
        else:
            append_to_pi_database(formatted_entries, PI_DATABASE_PATH)
    elif formatted_entries:
        print("\n  Run with --auto-save to append these to pi_database.md")
        print("  Run with --dry-run to preview the formatted entries\n")

    print(f"  Done. {len(ranked)} candidates above score threshold {args.min_score}.\n")


if __name__ == "__main__":
    main()
