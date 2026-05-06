# CLAUDE.md — PhD Application Automation for Arina
> **Read this file at the start of every session.**
> It contains Arina's full profile, all 6 PI records, proven PhD writing tips sourced from faculty
> and admissions experts, and precise instructions for every document type.

---

## Directory Map

```
phd_project/
├── CLAUDE.md                        ← this file (read first, every session)
├── cv.tex                           ← Arina's base LaTeX CV (NEVER rename or delete)
├── arina_profile.md                 ← extended profile, motivation draft, research notes
├── pi_database.md                   ← all 6 PI records with papers, emails, methods
├── motivation_tips.md               ← proven PhD motivation letter principles (sourced)
├── templates/
│   ├── cold_email.txt               ← cold email scaffold
│   ├── motivation_letter.tex        ← LaTeX motivation letter template
│   └── highlights_card.txt          ← talking points scaffold
├── outputs/
│   ├── emails/                      ← email_<slug>.txt
│   ├── motivation_letters/          ← motivation_<slug>.tex
│   ├── cv_variants/                 ← cv_<slug>.tex  (tailored from cv.tex)
│   └── highlights/                  ← highlights_<slug>.txt
└── pi_data/                         ← raw notes, downloaded papers (optional)
```

**PI slugs:** `prinz` · `haass` · `heneka` · `tahirovic` · `neher` · `destrooper`

---

## How to Use This Project in Claude Code

### Single PI — all 4 documents
```
Generate all application documents for Prof. Marco Prinz
```
Claude will produce and save:
- `outputs/emails/email_prinz.txt`
- `outputs/motivation_letters/motivation_prinz.tex`
- `outputs/cv_variants/cv_prinz.tex`
- `outputs/highlights/highlights_prinz.txt`

### Batch — all 6 PIs
```
Generate all documents for all 6 PIs
```

### Single document type
```
Write the cold email for Dr. Sabina Tahirovic
Tailor cv.tex for Prof. Christian Haass → save as cv_haass.tex
Write the motivation letter for Prof. Michael Heneka
Generate highlights card for Dr. Jonas Neher
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

### Compile a CV variant to PDF
```bash
cd outputs/cv_variants
pdflatex cv_prinz.tex
```

---

## Standing Generation Rules (apply to every document)

1. **Pull Arina's data from `arina_profile.md`** — do not use memory or invent details
2. **Pull PI data from `pi_database.md`** — only use confirmed papers, emails, and methods
3. **Apply the motivation writing principles in `motivation_tips.md`** for every letter
4. **Never fabricate** experience, publications, institutions, or dates
5. **Never use** the phrases: "I am writing to express my interest", "passion for science since childhood", "world-class institution", "highly motivated", "dream of becoming"
6. **Name actual antibodies, instruments, and techniques** — specificity is what separates good from great
7. **One document per PI slug** — always overwrite if regenerating
8. **LaTeX** — use `\jobhl{}` macro in CV variants to highlight PI-relevant keywords in teal

---

## CV LaTeX Quick Reference

- **File:** `cv.tex` — LaTeX, letterpaper, 11pt, sans-serif (tgheros)
- **Highlight macro:** `\jobhl{keyword}` → bold teal, used for PI-relevant terms
- **Entry macro:** `\resumeSubheading{Org}{Dates}{Role}{Location}`
- **Bullet macro:** `\resumeItem{text}`
- **Section order:** STATEMENT → EDUCATION → RESEARCH EXPERIENCE → SKILLS → PUBLICATIONS → CONFERENCES → HONOURS → LANGUAGES → REFERENCES
- **Most impactful edit per PI:** rewrite the STATEMENT OF RESEARCH INTEREST (3 sentences max, use PI's vocabulary)
- **Compile:** `pdflatex cv_<slug>.tex` (requires texlive-full, fontawesome5, FiraMono, tgheros)

---

*Last updated: May 2026 · See `arina_profile.md` for full CV details · See `pi_database.md` for PI records*
