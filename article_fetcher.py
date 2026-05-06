#!/usr/bin/env python3
"""
Article Fetcher for PhD Application PI Research
================================================
For each PI slug in pi_database.md, this script:
  1. Reads the PI's key-paper DOIs from pi_database.md
  2. Fetches full metadata from PubMed (title, abstract, authors, MeSH terms)
  3. Downloads the full-text PDF from open-access sources in priority order:
        PMC (PubMed Central) → Unpaywall → bioRxiv/medRxiv → Europe PMC
  4. Extracts text from the PDF and parses:
        • Methods section (antibody names, instrument models, software)
        • Key findings from abstract
        • Open questions from introduction/discussion
  5. Writes  pi_data/<slug>/articles.json   — raw metadata
             pi_data/<slug>/summary.md      — structured Claude-readable digest
             pi_data/<slug>/pdfs/*.pdf      — downloaded full texts

Usage
-----
  # Fetch for one PI:
  python article_fetcher.py prinz

  # Fetch for all PIs in pi_database.md:
  python article_fetcher.py --all

  # Re-fetch and overwrite existing summaries:
  python article_fetcher.py --all --overwrite

  # Fetch only metadata (no PDFs, faster):
  python article_fetcher.py --all --no-pdf

Requirements
------------
  pip install requests biopython

Optional (enables PDF text extraction):
  pip install pypdf

Environment variables:
  NCBI_EMAIL    — polite Entrez crawling (defaults to Arina's email)
  NCBI_API_KEY  — free key from ncbi.nlm.nih.gov/account → 10 req/s instead of 3
  UNPAYWALL_EMAIL — email for Unpaywall API (same as NCBI_EMAIL by default)

HOW CLAUDE USES THE OUTPUT
---------------------------
Before writing motivation_<slug>.tex or cv_<slug>.tex, Claude reads
pi_data/<slug>/summary.md and uses:
  • METHODS_QUOTES  → exact antibody/instrument/software names in P3 of letter
  • KEY_FINDINGS    → specific result to open P1 (the hook)
  • OPEN_QUESTIONS  → seed for P4 (forward-looking research direction)
  • TECHNIQUE_TABLE → cross-reference with Arina's skills for fit paragraph
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
import shutil
import hashlib
import argparse
import textwrap
from datetime import date
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    sys.exit("Missing: pip install requests")

try:
    from Bio import Entrez
except ImportError:
    sys.exit("Missing: pip install biopython")

# ─── Configuration ─────────────────────────────────────────────────────────────

PROJECT_ROOT      = Path(__file__).parent
PI_DATABASE_PATH  = PROJECT_ROOT / "pi_database.md"
PI_DATA_DIR       = PROJECT_ROOT / "pi_data"
ARINA_PROFILE     = PROJECT_ROOT / "arina_profile.md"

NCBI_EMAIL        = os.environ.get("NCBI_EMAIL", "arinazubair01@gmail.com")
NCBI_API_KEY      = os.environ.get("NCBI_API_KEY", "")
UNPAYWALL_EMAIL   = os.environ.get("UNPAYWALL_EMAIL", NCBI_EMAIL)

ENTREZ_DELAY = 0.34 if not NCBI_API_KEY else 0.11

# Arina's confirmed skill set — used for automatic overlap detection
ARINA_SKILLS = {
    "confocal microscopy":             "IGIB (Zeiss, z-stack, multi-channel)",
    "immunofluorescence":              "IGIB (Sox2, Tbr2, NeuN; systematic panel optimisation)",
    "fiji imagej":                     "IGIB + Chalmers (cell counting, morphometry, intensity)",
    "cryosection":                     "IGIB (embryonic E12–E16 + postnatal mouse brain)",
    "western blot":                    "ICGEB (lysis optimisation, ECL detection, anti-His)",
    "sds-page":                        "ICGEB + BRIC-THSTI",
    "elisa":                           "Rapture Biotech (blocking, calibration, standard curves)",
    "immunoprecipitation":             "Rapture Biotech",
    "affinity chromatography":         "ICGEB (Ni-NTA IMAC, imidazole gradient)",
    "pcr":                             "IGIB (genotyping, colony QC) + ICGEB",
    "mouse genotyping":                "IGIB (colony QC for developmental time-course)",
    "mouse handling":                  "IGIB (timed mating, embryo collection)",
    "flow cytometry":                  "indirect (Rapture Biotech immunoassay background)",
    "scanpy":                          "Chalmers (scRNA-seq, UMAP, DGE)",
    "scenic grnboost2":                "Chalmers (GRN inference across Braak stages)",
    "gsea":                            "Chalmers (pathway enrichment, GSEAPy)",
    "python":                          "Chalmers + coursework",
    "r":                               "coursework + data analysis",
    "scrna-seq":                       "Chalmers (analysis pipeline; no library prep)",
    "single-cell":                     "Chalmers (analysis pipeline; no library prep)",
    "spatial transcriptomics":         "Chalmers (analysis; no wet bench spatial work)",
}

# Regex patterns for method extraction
ANTIBODY_PATTERN  = re.compile(
    r"(?:anti[-\s]?\w[\w\-]*(?:\s*\([^)]{3,60}\))?|"      # anti-IBA1 (Wako, 1:500)
    r"\b(?:IBA1|TREM2|P2RY12|CD68|CD11b|GFAP|NeuN|Sox2|Tbr2|"
    r"Ki67|NLRP3|ASC|caspase|APP|PSD-?95|VGluT1|CX3CR1|"
    r"IBA-?1|Iba-?1|TMEM119|hCD68|6E10|ThioS?)\b"
    r"(?:\s+(?:antibody|Ab|staining|IF|immunostaining))?)",
    re.IGNORECASE,
)
INSTRUMENT_PATTERN = re.compile(
    r"\b(?:Zeiss\s+LSM[\s\w]*|Leica\s+SP[\s\w]*|Nikon\s+[A-Z\w]+|"
    r"Olympus\s+\w+|Zeiss\s+Axio\w*|STED|confocal|two-photon|"
    r"Seahorse\s+XF\w*|BD\s+\w+|Cytoflex|ImageStream|"
    r"Imaris|QuPath|CellProfiler|FlowJo|Fiji|ImageJ|Prism|"
    r"Chromium|MERFISH|Vizgen|Visium|RNAscope|NanoSight)",
    re.IGNORECASE,
)
SOFTWARE_PATTERN = re.compile(
    r"\b(?:Fiji|ImageJ|Imaris|QuPath|CellProfiler|FlowJo|GraphPad\s+Prism|"
    r"Scanpy|Seurat|SCENIC|GRNBoost2?|STAR|HISAT2|DESeq2|edgeR|"
    r"Bowtie|MACS2|HOMER|deepTools|cellranger|spaceranger|"
    r"GSEA|fgsea|GSEAPy|Velocyto|scVelo|Monocle|Harmony)\b",
    re.IGNORECASE,
)

# Section header patterns for locating Methods, Introduction, Discussion in PDFs
METHODS_HEADERS    = re.compile(r"(?:^|\n)(?:materials?\s+and\s+)?methods?(?:\s+and\s+materials?)?\s*\n", re.IGNORECASE)
INTRO_HEADERS      = re.compile(r"(?:^|\n)introduction\s*\n", re.IGNORECASE)
DISCUSSION_HEADERS = re.compile(r"(?:^|\n)discussion\s*\n", re.IGNORECASE)
RESULTS_HEADERS    = re.compile(r"(?:^|\n)results?\s*\n", re.IGNORECASE)
CONCLUSION_HEADERS = re.compile(r"(?:^|\n)conclusions?\s*\n", re.IGNORECASE)
REFERENCES_HEADERS = re.compile(r"(?:^|\n)references?\s*\n", re.IGNORECASE)


# ─── pi_database.md parser ─────────────────────────────────────────────────────

def parse_pi_database(db_path: Path) -> dict[str, dict]:
    """
    Parse pi_database.md and return a dict keyed by slug.
    Each value contains: name, institution, country, email, dois.
    """
    text = db_path.read_text(encoding="utf-8")
    pis: dict[str, dict] = {}

    # Split on PI section headers
    sections = re.split(r"^## PI-\d+", text, flags=re.MULTILINE)
    for section in sections[1:]:  # skip preamble
        slug_match  = re.search(r"\|\s*\*\*Slug\*\*\s*\|\s*`([^`]+)`", section)
        name_match  = re.search(r"\|\s*\*\*Full name\*\*\s*\|\s*(.+)", section)
        inst_match  = re.search(r"\|\s*\*\*Institution\*\*\s*\|\s*(.+)", section)
        cty_match   = re.search(r"\|\s*\*\*Country\*\*\s*\|\s*(.+)", section)
        email_match = re.search(r"\|\s*\*\*Email\*\*\s*\|\s*(.+)", section)

        if not slug_match:
            continue
        slug = slug_match.group(1).strip()

        # Extract DOIs from the section
        dois = re.findall(r"doi:\s*(10\.\S+)", section, re.IGNORECASE)
        dois = [d.rstrip(".,)>") for d in dois]

        pis[slug] = {
            "slug":        slug,
            "name":        name_match.group(1).strip()  if name_match  else slug,
            "institution": inst_match.group(1).strip()  if inst_match  else "",
            "country":     cty_match.group(1).strip()   if cty_match   else "",
            "email":       email_match.group(1).strip() if email_match else "",
            "dois":        dois,
        }
    return pis


# ─── PubMed metadata fetch ─────────────────────────────────────────────────────

def setup_entrez():
    Entrez.email   = NCBI_EMAIL
    Entrez.api_key = NCBI_API_KEY or None


def fetch_pubmed_by_doi(doi: str) -> Optional[dict]:
    """Return a dict of article metadata fetched from PubMed by DOI."""
    try:
        handle = Entrez.esearch(db="pubmed", term=f"{doi}[doi]", retmax=1)
        record = Entrez.read(handle)
        handle.close()
        time.sleep(ENTREZ_DELAY)
        pmids = record.get("IdList", [])
        if not pmids:
            return None
        return fetch_pubmed_by_pmid(pmids[0])
    except Exception as e:
        print(f"    [PubMed] Error searching {doi}: {e}")
        return None


def fetch_pubmed_by_pmid(pmid: str) -> Optional[dict]:
    """Fetch full article record for a single PMID."""
    try:
        handle = Entrez.efetch(db="pubmed", id=pmid, rettype="xml", retmode="xml")
        raw = handle.read()
        handle.close()
        time.sleep(ENTREZ_DELAY)
        return parse_pubmed_xml(raw, pmid)
    except Exception as e:
        print(f"    [PubMed] Error fetching PMID {pmid}: {e}")
        return None


def parse_pubmed_xml(xml_bytes: bytes, target_pmid: str) -> Optional[dict]:
    from xml.etree import ElementTree as ET
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    article_el = root.find(".//PubmedArticle")
    if article_el is None:
        return None

    def text(xpath: str, default: str = "") -> str:
        el = article_el.find(xpath)
        return "".join(el.itertext()).strip() if el is not None else default

    pmid  = text(".//PMID") or target_pmid
    title = text(".//ArticleTitle")
    jrnl  = text(".//Journal/Title") or text(".//MedlineTA")
    year  = text(".//PubDate/Year") or text(".//PubDate/MedlineDate")[:4]

    doi = ""
    pmc = ""
    for aid in article_el.findall(".//ArticleId"):
        if aid.get("IdType") == "doi":
            doi = aid.text or ""
        if aid.get("IdType") == "pmc":
            pmc = aid.text or ""

    authors = []
    affiliations = []
    for auth in article_el.findall(".//Author"):
        last = (auth.find("LastName")  or ET.Element("x")).text or ""
        fore = (auth.find("ForeName")  or ET.Element("x")).text or ""
        name = f"{fore} {last}".strip()
        if name:
            authors.append(name)
        for aff in auth.findall("AffiliationInfo/Affiliation"):
            if aff.text:
                affiliations.append(aff.text)

    abstract_parts = []
    for ab in article_el.findall(".//AbstractText"):
        label = ab.get("Label", "")
        part  = "".join(ab.itertext()).strip()
        abstract_parts.append(f"{label}: {part}" if label else part)
    abstract = " ".join(abstract_parts)

    mesh = [m.find("DescriptorName").text
            for m in article_el.findall(".//MeshHeading")
            if m.find("DescriptorName") is not None]

    return {
        "pmid": pmid, "doi": doi, "pmc": pmc,
        "title": title, "journal": jrnl, "year": year,
        "authors": authors, "affiliations": affiliations,
        "abstract": abstract, "mesh": mesh,
    }


# ─── Open-access PDF retrieval ─────────────────────────────────────────────────

def try_unpaywall(doi: str) -> Optional[str]:
    """Return open-access PDF URL via Unpaywall API, or None."""
    if not doi:
        return None
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        # Best OA location
        loc = data.get("best_oa_location") or {}
        pdf = loc.get("url_for_pdf") or loc.get("url")
        if pdf:
            return pdf
        # Fallback: iterate all locations
        for loc in data.get("oa_locations", []):
            pdf = loc.get("url_for_pdf")
            if pdf:
                return pdf
        return None
    except Exception:
        return None


def try_pmc(pmc_id: str) -> Optional[str]:
    """Return Europe PMC full-text PDF URL for a PMC ID, or None."""
    if not pmc_id:
        return None
    pmc_clean = pmc_id.replace("PMC", "")
    # Europe PMC PDF link
    return f"https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{pmc_clean}&blobtype=pdf"


def try_biorxiv(doi: str) -> Optional[str]:
    """Return bioRxiv PDF URL if this DOI belongs to a bioRxiv preprint."""
    if not doi or "biorxiv" not in doi and "medrxiv" not in doi:
        # Try the bioRxiv API to see if there's a preprint version
        try:
            r = requests.get(f"https://api.biorxiv.org/details/biorxiv/{doi}/na/json",
                             timeout=8)
            if r.status_code == 200:
                data = r.json()
                if data.get("collection"):
                    biorxiv_doi = data["collection"][0].get("doi", "")
                    if biorxiv_doi:
                        return f"https://www.biorxiv.org/content/{biorxiv_doi}.full.pdf"
        except Exception:
            pass
        return None
    # Direct bioRxiv PDF
    return f"https://www.biorxiv.org/content/{doi}.full.pdf"


def download_pdf(url: str, dest: Path, timeout: int = 30) -> bool:
    """Download a PDF from url to dest. Return True on success."""
    try:
        headers = {"User-Agent": f"PhD-Application-Bot/{NCBI_EMAIL}"}
        r = requests.get(url, headers=headers, timeout=timeout, stream=True)
        if r.status_code != 200:
            return False
        content_type = r.headers.get("Content-Type", "")
        if "pdf" not in content_type and "octet" not in content_type:
            # Might be HTML (paywall redirect) — check first bytes
            first = b""
            for chunk in r.iter_content(512):
                first = chunk
                break
            if not first.startswith(b"%PDF"):
                return False
            dest.write_bytes(first)
            for chunk in r.iter_content(8192):
                with open(dest, "ab") as f:
                    f.write(chunk)
            return True
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return dest.stat().st_size > 5_000  # at least 5 KB
    except Exception:
        return False


def fetch_pdf(meta: dict, pdf_dir: Path) -> Optional[Path]:
    """Try all open-access sources and return local PDF path on success."""
    doi = meta.get("doi", "")
    pmc = meta.get("pmc", "")
    safe_name = re.sub(r"[^\w.-]", "_", doi or meta.get("pmid", "unknown"))
    dest = pdf_dir / f"{safe_name}.pdf"

    if dest.exists() and dest.stat().st_size > 5_000:
        return dest

    pdf_dir.mkdir(parents=True, exist_ok=True)

    sources = []
    if pmc:
        sources.append(("PMC", try_pmc(pmc)))
    up_url = try_unpaywall(doi)
    if up_url:
        sources.append(("Unpaywall", up_url))
    bx_url = try_biorxiv(doi)
    if bx_url:
        sources.append(("bioRxiv", bx_url))

    for name, url in sources:
        if url:
            print(f"    [{name}] Downloading {doi[:40]}...", end=" ", flush=True)
            if download_pdf(url, dest):
                print("OK")
                return dest
            else:
                print("failed")

    return None


# ─── PDF text extraction ────────────────────────────────────────────────────────

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF. Returns empty string if pypdf not installed."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        pages  = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    except ImportError:
        return ""  # pypdf not installed — degrade gracefully
    except Exception:
        return ""


def extract_section(text: str, start_pattern: re.Pattern,
                    end_patterns: list[re.Pattern]) -> str:
    """Extract the text block between start_pattern and the first end_pattern."""
    m = start_pattern.search(text)
    if not m:
        return ""
    start = m.end()
    end   = len(text)
    for ep in end_patterns:
        em = ep.search(text, start)
        if em and em.start() < end:
            end = em.start()
    return text[start:end].strip()


def extract_methods_text(full_text: str) -> str:
    return extract_section(
        full_text,
        METHODS_HEADERS,
        [DISCUSSION_HEADERS, CONCLUSION_HEADERS, REFERENCES_HEADERS],
    )


def extract_intro_text(full_text: str) -> str:
    return extract_section(
        full_text,
        INTRO_HEADERS,
        [METHODS_HEADERS, RESULTS_HEADERS],
    )


def find_antibodies(text: str) -> list[str]:
    hits = []
    for m in ANTIBODY_PATTERN.finditer(text):
        val = m.group(0).strip()
        if len(val) > 3 and val not in hits:
            hits.append(val)
    return hits[:30]


def find_instruments(text: str) -> list[str]:
    hits = []
    for m in INSTRUMENT_PATTERN.finditer(text):
        val = m.group(0).strip()
        if val not in hits:
            hits.append(val)
    return hits[:20]


def find_software(text: str) -> list[str]:
    hits = []
    for m in SOFTWARE_PATTERN.finditer(text):
        val = m.group(0).strip()
        if val not in hits:
            hits.append(val)
    return hits[:15]


def extract_method_sentences(methods_text: str, max_sentences: int = 20) -> list[str]:
    """
    Extract sentences from the methods section that mention specific lab techniques.
    These become the most valuable quotes for the motivation letter.
    """
    technique_triggers = [
        "antibod", "stain", "confocal", "microscop", "imagej", "fiji", "imaris",
        "qupath", "cryosection", "western blot", "elisa", "flow cytom", "facs",
        "isolat", "culture", "transfect", "inject", "dissociat", "gradient",
        "immunoprecip", "affinity", "sort", "sequence", "library", "chromium",
        "spatial", "rnascope", "seahorse", "lysotracker", "phrodo",
    ]
    sentences = re.split(r"(?<=[.!?])\s+", methods_text)
    selected  = []
    for sent in sentences:
        sent_clean = sent.strip()
        if len(sent_clean) < 30:
            continue
        if any(t in sent_clean.lower() for t in technique_triggers):
            selected.append(sent_clean)
        if len(selected) >= max_sentences:
            break
    return selected


def extract_key_findings(abstract: str) -> list[str]:
    """
    Pull the 2–3 most result-like sentences from the abstract for the hook paragraph.
    """
    result_triggers = [
        "we found", "we show", "we demonstrate", "we identify", "we report",
        "revealed", "identified", "demonstrated", "showed", "uncovered",
        "our results", "our data", "these results", "together,", "collectively",
        "here we", "we describe",
    ]
    sentences = re.split(r"(?<=[.!?])\s+", abstract)
    findings  = []
    for sent in sentences:
        lower = sent.lower()
        if any(t in lower for t in result_triggers) and len(sent) > 40:
            findings.append(sent.strip())
        if len(findings) >= 3:
            break
    # Fallback: last 2 sentences of abstract
    if not findings and len(sentences) >= 2:
        findings = [s.strip() for s in sentences[-2:] if len(s.strip()) > 40]
    return findings


def extract_open_questions(text: str) -> list[str]:
    """
    Extract forward-looking sentences (questions, hypotheses) from introduction/discussion.
    Used for P4 of the motivation letter.
    """
    question_triggers = [
        "remains unclear", "remains unknown", "not yet understood", "open question",
        "future studies", "future work", "warrant further", "yet to be determined",
        "it is unclear", "it remains", "little is known", "poorly understood",
        "needs to be", "how microglia", "whether microglia", "the mechanism",
        "remain to be", "it will be important", "further investigation",
    ]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    questions = []
    for sent in sentences:
        lower = sent.lower()
        if any(t in lower for t in question_triggers) and len(sent) > 40:
            questions.append(sent.strip())
        if len(questions) >= 4:
            break
    return questions


def detect_arina_overlaps(methods_text: str, abstract: str) -> dict[str, str]:
    """
    Cross-reference extracted text against Arina's confirmed skill set.
    Returns a dict: skill_name → source_context.
    """
    full = (methods_text + " " + abstract).lower()
    overlaps = {}
    for skill, source in ARINA_SKILLS.items():
        if skill.lower() in full:
            overlaps[skill] = source
    return overlaps


# ─── Summary writer ─────────────────────────────────────────────────────────────

SUMMARY_TEMPLATE = """\
# PI Research Summary — {name} (`{slug}`)
> Auto-generated by `article_fetcher.py` on {today}
> **Read this file FIRST** before writing `motivation_{slug}.tex`, `cv_{slug}.tex`,
> or `email_{slug}.txt`. Use exact antibody names, instrument models, and findings below.

---

## Papers Fetched ({n_papers})

{paper_list}

---

## KEY FINDINGS (use in P1 — the hook)

{key_findings}

---

## OPEN QUESTIONS (use in P4 — forward-looking direction)

{open_questions}

---

## METHODS QUOTES (use in P3 — exact technique fit)
> Paste these verbatim or paraphrase with attribution in the motivation letter.
> Naming exact instruments/antibodies from the PI's own paper is the #1 differentiator.

{method_quotes}

---

## EXACT ANTIBODIES / MARKERS MENTIONED

{antibody_list}

---

## INSTRUMENTS & SOFTWARE MENTIONED

{instrument_list}

---

## ARINA'S CONFIRMED TECHNIQUE OVERLAPS
> These are Arina's skills that appear directly in the PI's methods.
> Highlight ALL of them in P3 of the letter and in the CV STATEMENT.

{overlap_table}

---

## RAW ABSTRACTS (reference if needed)

{abstracts}
"""


def write_summary(slug: str, pi_meta: dict, articles: list[dict],
                  pdf_extracts: dict[str, str], out_dir: Path) -> Path:
    """Write a structured summary.md for Claude to read before document generation."""

    all_abstracts = [a.get("abstract", "") for a in articles]
    all_methods   = list(pdf_extracts.values())

    combined_methods  = " ".join(all_methods)
    combined_abstract = " ".join(all_abstracts)

    # Key findings
    findings = []
    for a in articles:
        findings.extend(extract_key_findings(a.get("abstract", "")))
    findings = list(dict.fromkeys(findings))[:5]  # de-dup, keep top 5

    # Open questions from methods/abstracts (intro text not always available)
    questions = extract_open_questions(combined_methods + " " + combined_abstract)

    # Method sentences
    method_sents = []
    for mtext in all_methods:
        method_sents.extend(extract_method_sentences(mtext, max_sentences=10))
    method_sents = list(dict.fromkeys(method_sents))[:20]

    # Entities
    antibodies  = list(dict.fromkeys(find_antibodies(combined_methods + " " + combined_abstract)))
    instruments = list(dict.fromkeys(find_instruments(combined_methods + " " + combined_abstract)))
    software    = list(dict.fromkeys(find_software(combined_methods + " " + combined_abstract)))

    # Arina overlaps
    overlaps = detect_arina_overlaps(combined_methods, combined_abstract)

    # Format paper list
    paper_lines = []
    for a in articles:
        pdf_note = "PDF extracted ✓" if a.get("pmid") in pdf_extracts else "PDF unavailable"
        paper_lines.append(
            f"- **{a.get('title', 'Unknown')}**\n"
            f"  {a.get('journal', '')} {a.get('year', '')} | "
            f"DOI: {a.get('doi', '—')} | PMID: {a.get('pmid', '—')} | {pdf_note}"
        )

    # Format sections
    def bullets(items: list[str], indent: str = "") -> str:
        if not items:
            return f"{indent}— Not extracted (PDF unavailable or section not found)"
        return "\n".join(f"{indent}- {it}" for it in items)

    overlap_rows = []
    if overlaps:
        overlap_rows.append("| Skill | Arina's source |")
        overlap_rows.append("|---|---|")
        for skill, source in sorted(overlaps.items()):
            overlap_rows.append(f"| {skill} | {source} |")
    else:
        overlap_rows.append("— No overlaps auto-detected (may need manual review or PDF text extraction)")

    abstracts_block = "\n\n".join(
        f"### {a.get('title', 'Unknown')[:80]}\n{a.get('abstract', '—')}"
        for a in articles
    )

    content = SUMMARY_TEMPLATE.format(
        name       = pi_meta["name"],
        slug       = slug,
        today      = date.today().isoformat(),
        n_papers   = len(articles),
        paper_list = "\n".join(paper_lines) or "— None fetched",
        key_findings    = bullets(findings),
        open_questions  = bullets(questions),
        method_quotes   = bullets(method_sents[:15]),
        antibody_list   = bullets(antibodies) if antibodies
                         else "— See abstracts below or fetch PDF for extraction",
        instrument_list = (
            bullets(instruments, "")
            + ("\n\n**Software:**\n" + bullets(software) if software else "")
        ) if instruments or software else "— See abstracts below",
        overlap_table   = "\n".join(overlap_rows),
        abstracts       = abstracts_block or "— None available",
    )

    out_path = out_dir / "summary.md"
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ─── Per-PI pipeline ─────────────────────────────────────────────────────────────

def process_pi(slug: str, pi_meta: dict, fetch_pdfs: bool, overwrite: bool) -> bool:
    """Full pipeline for one PI. Returns True on success."""
    out_dir  = PI_DATA_DIR / slug
    pdf_dir  = out_dir / "pdfs"
    json_path = out_dir / "articles.json"
    summ_path = out_dir / "summary.md"

    if summ_path.exists() and not overwrite:
        print(f"  [{slug}] summary.md exists — skip (use --overwrite to re-fetch)")
        return True

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  ─── {pi_meta['name']} ({slug}) ───")

    dois = pi_meta.get("dois", [])
    if not dois:
        print(f"  [{slug}] No DOIs found in pi_database.md — skipping")
        return False

    # 1. Fetch PubMed metadata
    articles: list[dict] = []
    for doi in dois:
        print(f"    PubMed lookup: {doi[:55]}", end=" ... ", flush=True)
        meta = fetch_pubmed_by_doi(doi)
        if meta:
            articles.append(meta)
            print(f"OK ({meta.get('title','?')[:50]})")
        else:
            print("not found")
            # Store minimal stub so we don't lose the DOI
            articles.append({"doi": doi, "title": "— not in PubMed —",
                             "abstract": "", "pmid": "", "pmc": "", "year": "", "journal": ""})

    # 2. Save raw JSON
    json_path.write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3. Optionally download PDFs and extract text
    pdf_extracts: dict[str, str] = {}
    if fetch_pdfs:
        for art in articles:
            if not art.get("doi") and not art.get("pmc"):
                continue
            pdf_path = fetch_pdf(art, pdf_dir)
            if pdf_path:
                text = extract_pdf_text(pdf_path)
                if text:
                    pid = art.get("pmid") or art.get("doi", "")
                    pdf_extracts[pid] = text
                    print(f"    Extracted {len(text):,} chars from PDF")

    # 4. Write summary.md
    summ_path = write_summary(slug, pi_meta, articles, pdf_extracts, out_dir)
    print(f"    Saved → {summ_path.relative_to(PROJECT_ROOT)}")
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fetch PI articles from PubMed and generate pi_data/<slug>/summary.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python article_fetcher.py prinz
              python article_fetcher.py halle mancuso paolicelli
              python article_fetcher.py --all
              python article_fetcher.py --all --overwrite
              python article_fetcher.py --all --no-pdf
        """),
    )
    p.add_argument("slugs", nargs="*",
                   help="One or more PI slugs to process (e.g. prinz halle)")
    p.add_argument("--all",       action="store_true",
                   help="Process all PIs found in pi_database.md")
    p.add_argument("--overwrite", action="store_true",
                   help="Re-fetch and overwrite existing summary.md files")
    p.add_argument("--no-pdf",    action="store_true",
                   help="Skip PDF download; metadata and abstract only")
    return p


def main():
    args   = build_parser().parse_args()
    setup_entrez()

    if not PI_DATABASE_PATH.exists():
        sys.exit(f"pi_database.md not found at {PI_DATABASE_PATH}")

    all_pis = parse_pi_database(PI_DATABASE_PATH)

    if args.all:
        targets = list(all_pis.keys())
    elif args.slugs:
        targets = []
        for s in args.slugs:
            if s in all_pis:
                targets.append(s)
            else:
                print(f"  Warning: slug '{s}' not found in pi_database.md — skipping")
    else:
        build_parser().print_help()
        print(f"\n  Available slugs: {', '.join(sorted(all_pis.keys()))}")
        sys.exit(0)

    fetch_pdfs = not args.no_pdf

    print(f"\n  Article Fetcher — {len(targets)} PI(s) | PDFs: {'yes' if fetch_pdfs else 'no'}")
    print(f"  Output root: {PI_DATA_DIR}\n")

    ok, fail = 0, 0
    for slug in targets:
        try:
            success = process_pi(slug, all_pis[slug], fetch_pdfs, args.overwrite)
            if success:
                ok += 1
            else:
                fail += 1
        except Exception as e:
            print(f"  [{slug}] Unexpected error: {e}")
            fail += 1

    print(f"\n  Done. {ok} succeeded, {fail} failed.")
    print(f"  Summaries in: {PI_DATA_DIR}/\n")


if __name__ == "__main__":
    main()
