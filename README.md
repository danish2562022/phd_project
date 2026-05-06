# PhD Application Automation — Setup Guide

## What This Directory Does

For each of Arina's 6 EU target PIs, Claude Code generates 4 tailored documents:

| Document | Where it's saved |
|----------|-----------------|
| Cold email | `outputs/emails/email_<slug>.txt` |
| Motivation letter (LaTeX) | `outputs/motivation_letters/motivation_<slug>.tex` |
| Tailored CV (LaTeX) | `outputs/cv_variants/cv_<slug>.tex` |
| Talking points card | `outputs/highlights/highlights_<slug>.txt` |

PI slugs: `prinz` · `haass` · `heneka` · `tahirovic` · `neher` · `destrooper`

---

## Setup (one time)

1. **Copy this folder** to your machine — keep all files in the same directory
2. **Place `cv.tex`** in the root of this folder (same level as `CLAUDE.md`)
3. **Open the folder in Claude Code**: `claude` (in terminal, from this directory)
4. Claude Code reads `CLAUDE.md` automatically on startup

### Optional: personalise before generating
- Open `arina_profile.md` → update the **Motivation Draft** section with your own words
- Open `arina_profile.md` → update the **Research Data Notes** section with fresh results

---

## Commands to Use in Claude Code

### Generate everything for one PI
```
Generate all application documents for Prof. Marco Prinz
```
→ produces all 4 files for `prinz`

### Generate just one document type
```
Write the cold email for Dr. Sabina Tahirovic
Write the motivation letter for Prof. Michael Heneka
Tailor cv.tex for Prof. Christian Haass → save as outputs/cv_variants/cv_haass.tex
Generate highlights card for Dr. Jonas Neher
```

### Batch — all 6 PIs
```
Generate all documents for all 6 PIs
```

### Compile a CV variant to PDF
```bash
cd outputs/cv_variants
pdflatex cv_prinz.tex
```
Requires: `texlive-full` (or texlive + texlive-fonts-extra + texlive-science)

### Add a new PI
```
Add a new PI to pi_database.md:
Name: Prof. [Name]
Institution: [Institution]
Email: [email]
Focus: [research focus]
Key paper: [full citation]
Lab methods: [wet-lab techniques]
```

### Update Arina's profile and regenerate
```
Update arina_profile.md — add this new result: [paste your result/data]
Regenerate motivation_prinz.tex with the updated profile
```

---

## File Descriptions

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Master instruction file — Claude reads this every session |
| `cv.tex` | Base CV in LaTeX — source for all CV variants |
| `arina_profile.md` | Full CV details, motivation draft, research data notes |
| `pi_database.md` | All 6 PI records: paper, email, methods, fit analysis |
| `motivation_tips.md` | Proven PhD letter principles Claude applies to every letter |
| `templates/cold_email.txt` | Email scaffold |
| `templates/motivation_letter.tex` | LaTeX letter template |
| `templates/highlights_card.txt` | Talking points scaffold |
| `outputs/` | All generated files go here |

---

## LaTeX Requirements

Install on Ubuntu/Debian:
```bash
sudo apt-get install texlive-full
```

Install on macOS (via Homebrew):
```bash
brew install --cask mactex
```

Required packages (included in texlive-full):
- `fontawesome5`
- `FiraMono` (via `fira` package)
- `tgheros` (TeX Gyre Heros — sans serif)
- `contour`, `ulem`, `tabularx`, `enumitem`, `titlesec`

---

## Quick Checklist Before Sending Any Application

- [ ] CV variant compiled to PDF — no LaTeX errors
- [ ] PI's name and email spelled correctly
- [ ] Correct paper title and year in both email and motivation letter
- [ ] Arina's specific antibodies/instruments named (not just "IF experience")
- [ ] Forward-looking paragraph included in motivation letter
- [ ] Slides link correct (IGIB or Chalmers, depending on PI)
- [ ] Subject line of email is specific (not just "PhD Enquiry")
- [ ] npj Aging paper mentioned as under revision, not published

---

*Maintained by Arina · Do not share publicly · May 2026*
