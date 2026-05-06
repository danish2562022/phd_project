# CLAUDE.md — PhD Application Automation for Arina
> **Read this file at the start of every session.**
> It contains Arina's full profile, all 12 PI records, proven PhD writing tips sourced from faculty
> and admissions experts, and precise instructions for every document type.

---

## Directory Map

```
phd_project/
├── CLAUDE.md                        ← this file (read first, every session)
├── cv.tex                           ← Arina's base LaTeX CV (NEVER rename or delete)
├── arina_profile.md                 ← extended profile, motivation draft, research notes
├── pi_database.md                   ← all 12 PI records with papers, emails, methods
├── motivation_tips.md               ← proven PhD motivation letter principles (sourced)
├── article_fetcher.py               ← downloads PI papers → pi_data/<slug>/summary.md
├── pi_discovery_agent.py            ← finds new EU PI candidates via PubMed
├── templates/
│   ├── cold_email.txt               ← cold email scaffold
│   ├── motivation_letter.tex        ← LaTeX motivation letter template
│   └── highlights_card.txt          ← talking points scaffold
├── outputs/
│   ├── emails/                      ← email_<slug>.txt
│   ├── motivation_letters/          ← motivation_<slug>.tex
│   ├── cv_variants/                 ← cv_<slug>.tex  (tailored from cv.tex)
│   └── highlights/                  ← highlights_<slug>.txt
└── pi_data/
    └── <slug>/
        ├── articles.json            ← raw PubMed metadata for PI's papers
        ├── summary.md               ← ★ STRUCTURED DIGEST — READ THIS BEFORE WRITING
        └── pdfs/                    ← downloaded open-access full texts
```

**PI slugs (original 6):** `prinz` · `haass` · `heneka` · `tahirovic` · `neher` · `destrooper`
**PI slugs (6 new EU):** `halle` · `mancuso` · `eggen` · `paolicelli` · `sierra` · `kim`

---

## Recommended Workflow Before Writing Any Document

### Step 0 — Fetch articles for the PI (run once per PI)
```bash
# Fetch paper metadata + open-access PDFs + write summary.md:
python article_fetcher.py <slug>

# Example — all new EU PIs at once:
python article_fetcher.py halle mancuso eggen paolicelli sierra kim

# Metadata only (no PDFs, faster):
python article_fetcher.py <slug> --no-pdf

# Re-fetch to refresh an existing summary:
python article_fetcher.py <slug> --overwrite
```
This writes `pi_data/<slug>/summary.md` — a structured digest with:
- **KEY FINDINGS** → seed for P1 (the hook) in the letter
- **METHODS QUOTES** → exact antibody/instrument names for P3 (technique fit)
- **OPEN QUESTIONS** → seed for P4 (forward-looking direction)
- **ARINA'S TECHNIQUE OVERLAPS** → pre-computed match table

### Step 1 — Generate documents
```
Generate all application documents for Prof. Marco Prinz
```
Claude will automatically:
1. Read `pi_data/prinz/summary.md` if it exists
2. Read `arina_profile.md` and `pi_database.md`
3. Produce and save:
   - `outputs/emails/email_prinz.txt`
   - `outputs/motivation_letters/motivation_prinz.tex`
   - `outputs/cv_variants/cv_prinz.tex`
   - `outputs/highlights/highlights_prinz.txt`

### Batch — all 12 PIs
```
Generate all documents for all 12 PIs
```

### Single document type
```
Write the cold email for Dr. Annett Halle
Tailor cv.tex for Prof. Bart Eggen → save as cv_eggen.tex
Write the motivation letter for Dr. Renzo Mancuso
Generate highlights card for Prof. Rosa Chiara Paolicelli
```

### Update & regenerate
```
Update arina_profile.md with this new result: [paste data]
Regenerate motivation_prinz.tex with the updated profile
```

### Add a new PI
```
Add new PI: Name / Institution / Email / Focus / Key paper / Lab methods
```
Then run: `python article_fetcher.py <new_slug>` to populate pi_data/.

### Find more EU PIs
```bash
python pi_discovery_agent.py                    # default search across all topics
python pi_discovery_agent.py --country France   # filter by country
python pi_discovery_agent.py --auto-save        # append top candidates to pi_database.md
```

### Compile a CV variant to PDF
```bash
cd outputs/cv_variants
pdflatex cv_prinz.tex
```

---

## Standing Generation Rules (apply to every document)

1. **Check `pi_data/<slug>/summary.md` FIRST** — if it exists, read it before writing anything.
   Use the exact antibody names, instrument model numbers, and quoted sentences from the methods
   section. This is the #1 quality lever: specificity that only comes from reading their actual paper.

2. **Pull Arina's data from `arina_profile.md`** — do not use memory or invent details.

3. **Pull PI data from `pi_database.md`** — only use confirmed papers, emails, and methods.

4. **Apply the motivation writing principles in `motivation_tips.md`** for every letter.

5. **Never fabricate** experience, publications, institutions, or dates.

6. **Never use** the phrases: "I am writing to express my interest", "passion for science since
   childhood", "world-class institution", "highly motivated", "dream of becoming",
   "groundbreaking work", "prestigious lab", "I am thrilled/excited".

7. **Never use em dashes ( — ).** Zero exceptions. Every em dash must become one of:
   a comma, a colon, a semicolon, or parentheses. This applies to motivation letters,
   cold emails, CV text, and highlights cards.

8. **Tone: European academic collegial, not US/UK formal.** Direct sentences, no flattery,
   no hedging. See `motivation_tips.md` for the full tone guide and country-by-country
   salutation rules. Key rules:
   - Closing: "Best regards," not "Yours sincerely,"
   - Denmark (kim): "Dear Thomas," is correct even for first contact
   - No flattery: describe what they found scientifically, not how impressive they are
   - No hedging: "My IF work maps directly onto your protocol" not "I believe I might be able to"

9. **Name actual antibodies, instruments, and techniques.** If `summary.md` contains a sentence
   like "We stained sections with anti-IBA1 (Wako, 019-19741, 1:500)", use those exact details
   in P3 of the letter.

10. **One document per PI slug** — always overwrite if regenerating.

11. **LaTeX** — use `\jobhl{}` macro in CV variants to highlight PI-relevant keywords in teal.

---

## How summary.md Feeds Each Document Section

| summary.md section | Used in |
|---|---|
| KEY FINDINGS | Motivation letter P1 (hook — cite the finding, not just the paper title) |
| OPEN QUESTIONS | Motivation letter P4 (forward-looking research direction) |
| METHODS QUOTES | Motivation letter P3 (exact technique overlap), cold email P2 |
| EXACT ANTIBODIES | CV STATEMENT highlight + letter P3 ("…the same IBA1/P2RY12 panel…") |
| INSTRUMENTS | Letter P3 ("…your Zeiss LSM 980 AiryScan pipeline…") |
| ARINA'S OVERLAPS | CV SKILLS section — reorder to put matching skills first for this PI |

---

## CV LaTeX Quick Reference

- **File:** `cv.tex` — LaTeX, letterpaper, 11pt, sans-serif (tgheros)
- **Highlight macro:** `\jobhl{keyword}` → bold teal, used for PI-relevant terms
- **Entry macro:** `\resumeSubheading{Org}{Dates}{Role}{Location}`
- **Bullet macro:** `\resumeItem{text}`
- **Section order:** STATEMENT → EDUCATION → RESEARCH EXPERIENCE → SKILLS → PUBLICATIONS → CONFERENCES → HONOURS → LANGUAGES → REFERENCES
- **Most impactful edit per PI:** rewrite the STATEMENT OF RESEARCH INTEREST (3 sentences max,
  use PI's vocabulary; seed from `summary.md` KEY FINDINGS and ARINA'S OVERLAPS)
- **Compile:** `pdflatex cv_<slug>.tex` (requires texlive-full, fontawesome5, FiraMono, tgheros)

---

## Motivation Letter — Paragraph-by-Paragraph Guide

| Para | Length | Source material |
|---|---|---|
| **P1 Hook** | 3–4 sentences | `summary.md` → KEY FINDINGS: cite a specific result from the PI's own paper |
| **P2 Research arc** | 4–5 sentences | `arina_profile.md` → IGIB → Chalmers → why this PI is the next step |
| **P3 Technique fit** | 4–5 sentences | `summary.md` → METHODS QUOTES + EXACT ANTIBODIES + INSTRUMENTS |
| **P4 Forward-looking** | 3–4 sentences | `summary.md` → OPEN QUESTIONS, linked to Arina's Chalmers GRN findings |
| **P5 Close** | 2 sentences | Clear ask: PhD position / brief call; attach CV and slides links |

---

*Last updated: May 2026 · See `arina_profile.md` for full CV details · See `pi_database.md` for PI records*
