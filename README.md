# Eightfold Candidate Transformer

A production-ready Python pipeline that ingests candidate data from **multiple CSV rows** and **multiple resume PDFs**, matches records across sources, normalizes and merges conflicting information, tracks full provenance, assigns confidence scores, and exports an array of canonical candidate profiles in JSON.

---

## Project Overview

Recruiting teams receive candidate data from both structured exports (CSV) and unstructured documents (PDF resumes). This pipeline:

1. Extracts **one record per CSV row** and **one record per resume PDF**
2. **Normalizes** emails, phones, skills, and dates — tracking every decision as provenance
3. **Matches** records across sources: email → phone → name (strict priority)
4. **Merges** matched records using confidence-based conflict resolution
5. **Validates** all fields: email format, E.164 phones, confidence ranges, required fields
6. **Exports** `output/profiles.json` — an array of canonical candidate profiles

Built with Python 3.11, pandas, Pydantic v2, pdfplumber, phonenumbers, and python-dateutil.

---

## Architecture

```
┌─────────────────┐     ┌──────────────────────┐
│  CSV (multi-row)│     │  Resume folder (PDFs) │
└────────┬────────┘     └──────────┬───────────┘
         │                         │
         ▼                         ▼
┌─────────────────┐     ┌──────────────────────┐
│  CSVExtractor   │     │  ResumeExtractor     │
│  (adapter)      │     │  (adapter)           │
└────────┬────────┘     └──────────┬───────────┘
         │                         │
         └──────────┬──────────────┘
                    ▼
           ┌────────────────┐
           │  Normalizers   │
           │ email/phone/   │
           │ skill/date     │
           └────────┬───────┘
                    ▼
           ┌────────────────┐
           │  Matcher       │
           │ email→phone→   │
           │ name (indexed) │
           └────────┬───────┘
                    ▼
           ┌────────────────┐
           │  Merge Engine  │
           │ (confidence)   │
           └────────┬───────┘
                    ▼
           ┌────────────────┐
           │  Confidence    │
           │  Scoring       │
           └────────┬───────┘
                    ▼
           ┌────────────────┐
           │  Validator     │
           └────────┬───────┘
                    ▼
           ┌────────────────┐
           │  Projector     │
           │  (optional)    │
           └────────┬───────┘
                    ▼
           ┌────────────────┐
           │ profiles.json  │
           │  [profile, …]  │
           └────────────────┘
```

New sources (LinkedIn, ATS, notes) can be added by implementing the `BaseExtractor` adapter — no pipeline changes needed.

---

## Folder Structure

```
eightfold-candidate-transformer/
├── src/
│   ├── main.py                 # CLI entry point
│   ├── models.py               # Pydantic schemas (Candidate, ProvenanceEntry, …)
│   ├── common.py               # Shared utilities and normalization wiring
│   ├── matcher.py              # Cross-source matching (Union-Find + hash indexes)
│   ├── merger.py               # Multi-source merge with conflict resolution
│   ├── confidence.py           # Source and field confidence scoring
│   ├── projector.py            # Config-driven output projection
│   ├── validator.py            # Email, phone, confidence, and schema validation
│   ├── extractors/
│   │   ├── base.py             # BaseExtractor adapter interface
│   │   ├── csv_extractor.py    # Multi-row CSV extraction
│   │   └── resume_extractor.py # Single + folder PDF extraction (regex)
│   └── normalizers/
│       ├── email_normalizer.py # Trim, lowercase, validate, dedup + provenance
│       ├── phone_normalizer.py # E.164 conversion, validation, dedup + provenance
│       ├── skill_normalizer.py # Alias mapping, dedup + provenance
│       └── date_normalizer.py  # YYYY-MM normalization
├── input/
│   ├── candidate.csv           # Sample multi-candidate CSV
│   ├── config.json             # Optional output projection config
│   ├── resume.pdf              # Sample resume PDF
│   └── resumes/                # Folder for additional resume PDFs
├── output/
│   ├── sample_profile.json     # Example single-candidate output
│   └── sample_profiles.json    # Example multi-candidate output
├── scripts/
│   └── generate_stress_csv.py  # Generates 10,000-row stress test CSV
├── tests/                      # 76 tests (unit + integration + stress)
│   ├── conftest.py
│   ├── helpers.py
│   ├── test_csv_extractor.py
│   ├── test_email_normalizer.py
│   ├── test_experience_extractor.py
│   ├── test_matcher.py
│   ├── test_matching_edge_cases.py
│   ├── test_merger.py
│   ├── test_multi_candidate.py
│   ├── test_output_validation.py
│   ├── test_phone_normalizer.py
│   ├── test_pipeline.py
│   ├── test_projector.py
│   ├── test_provenance.py
│   ├── test_resume_extractor.py
│   ├── test_skill_normalizer.py
│   ├── test_stress.py
│   └── test_validator.py
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Installation

**Requirements:** Python 3.11+

```bash
git clone <repo-url>
cd eightfold-candidate-transformer
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Usage

### CSV only (multiple candidates)

```bash
python3 src/main.py --csv input/candidate.csv
```

### CSV + resume folder

```bash
python3 src/main.py --csv input/candidate.csv --resumes input/resumes/
```

### Single resume + CSV

```bash
python3 src/main.py --csv input/candidate.csv --resume input/resume.pdf
```

### With output projection config

```bash
python3 src/main.py \
  --csv input/candidate.csv \
  --resumes input/resumes/ \
  --config input/config.json
```

### Custom output path

```bash
python3 src/main.py --csv input/candidate.csv --output output/my_profiles.json
```

---

## Example Commands

```bash
# Run the full pipeline
python3 src/main.py --csv input/candidate.csv --resumes input/resumes/

# Run all tests
pytest tests/ -v

# Run tests (excluding slow stress test)
pytest tests/ -v --ignore=tests/test_stress.py

# Generate 10,000-row stress test dataset
python3 scripts/generate_stress_csv.py

# Run pipeline against stress dataset
python3 src/main.py --csv input/candidate_10000.csv --output output/profiles.json
```

---

## Example Input

**`input/candidate.csv`** — one row per candidate:

```csv
name,email,phone,current_company,title
John Doe,john.doe@gmail.com,9999999999,Google,Software Engineer
Priya Sharma,priya.sharma@gmail.com,+91 9876543210,Microsoft,Data Analyst
```

**`input/resumes/`** — one PDF per candidate:

```
John_Doe.pdf
Priya_Sharma.pdf
```

---

## Example Output

**`output/profiles.json`** — array of canonical profiles:

```json
[
  {
    "candidate_id": "40a437ea-9c60-4cc7-a107-53caa7ef27f9",
    "full_name": "John Doe",
    "emails": ["john.doe@gmail.com"],
    "phones": ["+919876543210"],
    "skills": ["Python", "React"],
    "experience": [
      {
        "company": "Google",
        "title": "Software Engineer",
        "start_date": null,
        "end_date": null,
        "description": null
      }
    ],
    "education": [],
    "overall_confidence": 0.89,
    "provenance": [
      {
        "field": "full_name",
        "source": "candidate.csv",
        "method": "csv column mapping",
        "details": null
      },
      {
        "field": "phones",
        "source": "candidate.csv",
        "method": "normalization",
        "details": "phone converted to E.164: 9876543210 -> +919876543210"
      }
    ]
  }
]
```

See `output/sample_profiles.json` for a full generated example.

---

## Matching Strategy

Records are grouped using a **strict priority-based policy**:

| Priority | Key | Condition |
|----------|-----|-----------|
| 1 | Email (normalized) | Both records have emails → match only on email overlap |
| 2 | Phone (E.164) | At least one record lacks email → match on phone |
| 3 | Full name | Both records lack email **and** phone → match on exact normalized name |

### Critical Safety Rule

> **Candidates with different emails are never merged** — regardless of shared phone or name.

This is enforced at two levels:

1. **Match-time**: `_records_match()` returns `None` when both sides have emails that don't overlap.
2. **Post-merge validation**: `_split_on_conflicting_emails()` splits any group where members have conflicting emails after Union-Find grouping — protecting against transitive merge violations.

---

## Conflict Resolution Strategy

When multiple sources provide data for the same candidate:

| Field type | Resolution |
|-----------|------------|
| Scalar (name, headline, years_experience) | Highest-confidence source wins |
| Lists (emails, phones, skills) | Union all values, then normalize and deduplicate |
| Nested (experience, education) | Concatenate from all sources |

All decisions are recorded in the `provenance` array.

---

## Confidence Scoring

### Source Confidence

| Source | Base score |
|--------|-----------|
| CSV | 0.95 |
| Resume | 0.85 |
| Notes (future) | 0.70 |

### Field Weights

| Field | Weight |
|-------|--------|
| full_name | 1.00 |
| emails | 0.98 |
| phones | 0.95 |
| skills | 0.88 |
| headline | 0.85 |
| experience | 0.82 |
| education | 0.80 |
| years_experience | 0.80 |
| location | 0.75 |
| links | 0.70 |

### Formula

```
field_score(f)     = source_confidence × field_weight(f)
overall_confidence = mean(field_scores for all populated fields)
                     clamped to [0, 1], rounded to 2 decimal places
```

Each profile includes both `overall_confidence` and `field_confidence` (per-field scores).

---

## Provenance Tracking

Every field in the output carries provenance entries recording:

| Property | Example |
|----------|---------|
| `field` | `"emails"` |
| `source` | `"candidate.csv"` |
| `method` | `"csv column mapping"` / `"regex extraction"` / `"normalization"` |
| `details` | `"email lowercased: ALICE@EXAMPLE.COM -> alice@example.com"` |

### Normalization decisions tracked

```
email lowercased: RAHUL.VERMA@gmail.com -> rahul.verma@gmail.com
invalid email removed: not-an-email
duplicate email removed: alice@example.com
phone converted to E.164: 9876543210 -> +919876543210
invalid phone removed: 123
duplicate phone removed: +919876543210
skill normalized: reactjs -> React
duplicate skill removed: Python
```

---

## Edge Cases Handled

| Scenario | Behaviour |
|----------|-----------|
| Missing CSV / resume / config | Warning logged; continues with available sources |
| Corrupted or empty PDF | Skipped with warning |
| Empty CSV or empty rows | Skipped gracefully |
| Duplicate CSV rows | Deduplicated by email + phone + name |
| Missing columns in CSV | Available fields extracted |
| Invalid phone numbers | Removed; provenance entry recorded |
| Invalid email addresses | Removed; provenance entry recorded |
| All-same-digit phones (e.g. `0000000000`) | Blocked by fake-number filter |
| Same phone, different emails | Never merged (email takes priority) |
| Same name, different emails | Never merged |
| Transitive email conflict via Union-Find | Post-merge validation splits the group |
| Multiple resumes for the same candidate | Merged via matcher |
| Duplicate skills / emails / phones | Deduplicated during normalization |
| Invalid JSON projection config | Warning; default output shape used |
| Unsupported file formats in resume folder | Skipped with warning |
| Null values / blank strings | Treated as missing; skipped gracefully |
| Extra whitespace in CSV cells | Trimmed during normalization |
| Uppercase emails | Lowercased; provenance entry recorded |

---

## Stress Testing

The pipeline is benchmarked against a 10,000+ row synthetic dataset.

### Generate the dataset

```bash
python3 scripts/generate_stress_csv.py
```

This creates `input/candidate_10000.csv` containing:
- 9,000 valid candidates
- 1,000 edge cases (missing fields, invalid phones/emails, blanks, duplicates, whitespace)
- 50 intentional duplicate rows

### Run the stress test

```bash
pytest tests/test_stress.py -v -s
```

### Benchmark results

| Metric | Value |
|--------|-------|
| Input rows | 10,050 |
| Profiles generated | ~9,365 |
| Execution time | ~2.5 s |
| Throughput | ~4,000 rows / sec |

> The stress CSV is excluded from version control (see `.gitignore`) to keep the repository lightweight. Always regenerate it with the script above.

---

## Assumptions

1. Default phone region is **India (`IN`)** for numbers without country codes.
2. CSV has **one candidate per row**; exact-duplicate rows (same email + phone + name) are skipped.
3. Resume PDFs contain machine-readable text (not scanned images).
4. Name matching (priority 3) is used **only** when both records lack email and phone.
5. Validation warnings are logged; the pipeline continues processing remaining candidates.
6. Confidence scores are deterministic — identical inputs always produce identical outputs.

---

## Future Improvements

- NLP/ML resume parsing for richer name and experience extraction
- Fuzzy name matching with a configurable similarity threshold
- Configurable phone region via CLI flag
- Database persistence and profile versioning
- REST API wrapper for streaming ingestion
- Additional extractors: LinkedIn, ATS exports, recruiter notes
- Parallel extraction for large resume folders
- Docker image for one-command deployment

---

## License

MIT
