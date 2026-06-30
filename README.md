# Eightfold Candidate Transformer

A robust and extensible Python pipeline that ingests candidate data from **multiple CSV rows**, **ATS JSON exports**, and **multiple resume PDFs**, matches records across sources, normalizes and merges conflicting information, tracks full provenance, assigns confidence scores, and exports an array of canonical candidate profiles in JSON.
The system is designed to be deterministic, explainable, extensible, and resilient to malformed or incomplete inputs.

---

## Project Overview

Recruiting teams receive candidate data from structured exports (CSV, ATS JSON) and unstructured documents (PDF resumes). This pipeline:

1. Extracts **one record per CSV row**, **one record per ATS JSON entry**, and **one record per resume PDF**
2. **Normalizes** emails, phones, skills, and dates — tracking every decision as provenance
3. **Matches** records across all sources: email → phone → name (strict priority)
4. **Merges** matched records using confidence-based conflict resolution
5. **Validates** all fields: email format, E.164 phones, confidence ranges, required fields
6. **Exports** `output/profiles.json` — an array of canonical candidate profiles

Built with Python 3.11, pandas, Pydantic v2, pdfplumber, phonenumbers, and python-dateutil.

## Assignment Requirements Coverage

-  Structured source 1: Recruiter CSV export
-  Structured source 2: ATS JSON export (field mapping: candidateName, mail, mobile, designation, organization, skills)
-  Unstructured source: Resume PDF extraction
-  Canonical candidate profile generation
-  Cross-source matching and deduplication (CSV ↔ ATS ↔ Resume)
-  Email, phone, skill, and date normalization
-  Provenance tracking for every field
-  Confidence scoring (CSV=0.95, ATS=0.90, Resume=0.85)
-  Configurable output projection
-  Schema validation
-  Graceful degradation on malformed or missing inputs
-  Stress tested on 10,000+ candidate records

---

## Architecture


┌──────────────────────────────────────────────────────────────┐
│                         INPUT SOURCES                        │
├──────────────────────────────────────────────────────────────┤
│  CSV Export            ATS JSON          Resume PDFs         │
│ (structured)         (structured)      (unstructured)        │
└──────────────┬──────────────┬───────────────────────┬───────-┘
               │              │                       │
               ▼              ▼                       ▼

┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  CSVExtractor   │  │  ATSExtractor   │  │ResumeExtractor  │
│   (Adapter)     │  │   (Adapter)     │  │   (Adapter)     │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         └────────────────────┼────────────────────┘
                              ▼

┌──────────────────────────────────────────────────────────────┐
│                  Canonical Candidate Model                   │
│          Convert all sources to a common schema              │
└──────────────────────────────┬──────────────────────────────-┘
                               ▼

┌──────────────────────────────────────────────────────────────┐
│                     Normalization Layer                      │
├──────────────────────────────────────────────────────────────┤
│ • Email normalization (lowercase, deduplication)             │
│ • Phone normalization (E.164 format)                         │
│ • Skill canonicalization (ReactJS → React)                   │
│ • Date normalization                                         │
└──────────────────────────────┬──────────────────────────────-┘
                               ▼

┌──────────────────────────────────────────────────────────────┐
│                      Matching Engine                         │
├──────────────────────────────────────────────────────────────┤
│ Matching priority:                                           │
│ 1. Email                                                     │
│ 2. Phone                                                     │
│ 3. Name                                                      │
│                                                              │
│ Uses indexed lookups for scalable matching.                  │
└──────────────────────────────┬──────────────────────────────-┘
                               ▼

┌──────────────────────────────────────────────────────────────┐
│                    Merge & Conflict Resolver                 │
├──────────────────────────────────────────────────────────────┤
│ • Merge records belonging to same candidate                  │
│ • Resolve conflicting values using source confidence         │
│ • Deduplicate skills, emails, and phones                     │
└──────────────────────────────┬──────────────────────────────-┘  
                               ▼

┌──────────────────────────────────────────────────────────────┐
│                    Provenance Tracker                        │
├──────────────────────────────────────────────────────────────┤
│ Track for every field:                                       │
│ • Source of value                                            │
│ • Extraction method                                          │
│ • Normalization decisions                                    │
└──────────────────────────────┬──────────────────────────────-┘
                               ▼

┌──────────────────────────────────────────────────────────────┐
│                    Confidence Engine                         │
├──────────────────────────────────────────────────────────────┤
│ Assign confidence scores based on:                           │
│ • Source reliability                                         │
│ • Data completeness                                          │
│ • Cross-source agreement                                     │
└──────────────────────────────┬──────────────────────────────-┘
                               ▼

┌──────────────────────────────────────────────────────────────┐
│                      Validation Layer                        │
├──────────────────────────────────────────────────────────────┤
│ • Required field checks                                      │
│ • Email validation                                           │
│ • Phone validation                                           │
│ • Confidence range validation                                │
│ • Duplicate detection                                        │
└──────────────────────────────┬──────────────────────────────-┘
                               ▼

┌──────────────────────────────────────────────────────────────┐
│                   Projection / Output Layer                  │
├──────────────────────────────────────────────────────────────┤
│ Runtime configurable output:                                 │
│ • Select fields                                              │
│ • Rename fields                                              │
│ • Include/Exclude confidence                                 │
│ • Handle missing values                                      │
└──────────────────────────────┬──────────────────────────────-┘
                               ▼

┌──────────────────────────────────────────────────────────────┐
│                      OUTPUT PROFILES                         │
│                      profiles.json                           │
└──────────────────────────────────────────────────────────────┘


Extensibility:
New sources (LinkedIn, GitHub, recruiter notes, etc.) can be
added by implementing the BaseExtractor interface without
modifying the downstream pipeline.


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
│   │   ├── __init__.py
│   │   ├── base.py             # BaseExtractor adapter interface
│   │   ├── ats_extractor.py    # ATS JSON extraction + field mapping
│   │   ├── csv_extractor.py    # Multi-row CSV extraction
│   │   └── resume_extractor.py # Single + folder PDF extraction (regex)
│   └── normalizers/
│       ├── email_normalizer.py # Trim, lowercase, validate, dedup + provenance
│       ├── phone_normalizer.py # E.164 conversion, validation, dedup + provenance
│       ├── skill_normalizer.py # Alias mapping, dedup + provenance
│       └── date_normalizer.py  # YYYY-MM normalization
├── input/
│   ├── ats.json                # Sample ATS JSON export
│   ├── candidate.csv           # Sample multi-candidate CSV
│   ├── config.json             # Optional projection config
│   ├── resume.pdf              # Sample resume PDF (152 KB)
│   └── resumes/
│       └── .gitkeep        # Folder for additional resume PDFs
├── output/
│   ├── sample_profile.json     # Example single-candidate output
│   └── sample_profiles.json    # Example multi-candidate output
├── scripts/
│   └── generate_stress_csv.py  # Generates 10,000-row stress test CSV
├── tests/                      # 107 tests (unit + integration + stress)
│   ├── conftest.py
│   ├── helpers.py
│   ├── test_ats_extractor.py
│   ├── test_ats_integration.py
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

### ATS JSON only

```bash
python3 src/main.py --ats input/ats.json
```

### CSV + ATS (most common)

```bash
python3 src/main.py --csv input/candidate.csv --ats input/ats.json
```

### CSV + ATS + resume folder (all three sources)

```bash
python3 src/main.py \
  --csv input/candidate.csv \
  --ats input/ats.json \
  --resumes input/resumes/
```

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
  --ats input/ats.json \
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
# Run the full pipeline (CSV + ATS + resumes)
python3 src/main.py --csv input/candidate.csv --ats input/ats.json --resumes input/resumes/

# ATS only
python3 src/main.py --ats input/ats.json

# Run all tests
python3 scripts/generate_stress_csv.py   # generate stress dataset first
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

**`input/ats.json`** — ATS export with non-canonical field names:

```json
[
  {
    "candidateName": "Priya Sharma",
    "mail": "priya.sharma@gmail.com",
    "mobile": "+91 9876543210",
    "designation": "Senior Software Engineer",
    "organization": "Infosys",
    "skills": ["Python", "Java", "ReactJS"]
  }
]
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

## Complexity Analysis

| Stage | Complexity |
|--------|------------|
| CSV Extraction | O(n) |
| ATS Extraction | O(n) |
| Resume Extraction | O(r) |
| Normalization | O(n) |
| Matching (indexed) | O(n) |
| Merge | O(n) |
| Validation | O(n) |

Where:
- n = number of candidate records
- r = number of resume PDFs

The matching engine uses hash indexes and Union-Find grouping, allowing the pipeline to scale efficiently to thousands of candidates.

## Conflict Resolution Strategy

When multiple sources provide data for the same candidate:

| Field type | Resolution |
|-----------|------------|
| Scalar (name, headline, years_experience) | Highest-confidence source wins |
| Lists (emails, phones, skills) | Union all values, then normalize and deduplicate |
| Nested (experience, education) | Concatenate from all sources |

All decisions are recorded in the `provenance` array.

---

## ATS JSON Field Mapping

The ATS extractor maps non-canonical ATS field names to the canonical pipeline schema:

| ATS Field | Canonical Field | Notes |
|-----------|----------------|-------|
| `candidateName` | `full_name` | Direct string mapping |
| `mail` | `emails` | Lowercased + validated |
| `mobile` | `phones` | Normalized to E.164 |
| `designation` | `experience[].title` | Packed into ExperienceEntry |
| `organization` | `experience[].company` | Packed into ExperienceEntry |
| `skills` | `skills[]` | Alias-normalized (e.g. ReactJS → React) |

Skills may be provided as a JSON array **or** a comma-separated string — both are handled.

All ATS provenance entries carry `"method": "ATS field mapping"` for full traceability.

---

## Confidence Scoring

### Source Confidence

| Source | Base score |
|--------|-----------|
| CSV | 0.95 |
| ATS | 0.90 |
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
## Key Design Decisions

### Adapter Pattern for Source Extensibility
Each source implements the `BaseExtractor` interface. New sources can be integrated without modifying the core pipeline.

### Strict Identity Matching Policy
Email is treated as the strongest identity signal. Candidates with conflicting emails are never merged, even if names or phone numbers match.

### Provenance-First Architecture
Every extraction, normalization, and merge decision is recorded in provenance metadata, making the system fully explainable and auditable.

### Deterministic Processing
Identical inputs always produce identical outputs, ensuring reproducibility and simplifying debugging.

## Future Improvements

- NLP/ML resume parsing for richer name and experience extraction
- Fuzzy name matching with a configurable similarity threshold
- Configurable phone region via CLI flag
- Database persistence and profile versioning
- REST API wrapper for streaming ingestion
- Additional extractors: LinkedIn profiles, recruiter notes, CRM exports
- Parallel extraction for large resume folders
- Docker image for one-command deployment

---


