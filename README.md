# FNOL Autonomous Insurance Claims Processing Agent

An autonomous agent that processes First Notice of Loss (FNOL) documents — extracting structured fields, identifying missing data, classifying the claim, and routing it to the correct workflow.

---

## Features

- **Dual extraction strategy**: Uses `pdfplumber` for text-layer PDFs and falls back to `pytesseract` OCR (via `pdf2image`) for image-based or scanned PDFs — handles both automatically.
- **Field extraction**: Extracts all FNOL fields defined in the assessment brief (policy info, incident info, involved parties, asset details).
- **Missing field detection**: Reports every mandatory field that is absent or blank.
- **Intelligent routing** with four rules:
  | Rule | Route |
  |------|-------|
  | Description contains fraud keywords (`fraud`, `staged`, `inconsistent`, …) | Investigation Flag |
  | Claim type = injury | Specialist Queue |
  | Any mandatory field missing | Manual Review |
  | Estimated damage < ₹25,000 | Fast-track |
- **JSON output**: One result file per input PDF + a combined `summary.json`.
- **34 unit + integration tests** covering field extraction, routing logic, edge cases, and PDF processing.

---

## Project Structure

```
fnol_agent/
├── agent.py            # Main agent — run this
├── requirements.txt    # Python dependencies
├── README.md
├── input_docs/         # Place your FNOL PDF/TXT files here
│   ├── sample.pdf      # Empty ACORD form (all fields blank)
│   └── sample1.pdf     # Filled ACORD form (amit sharma)
└── tests/
    ├── __init__.py
    └── test_agent.py   # 34 unit + integration tests
```

---

## Prerequisites

### 1. Python
Python 3.10 or higher.

### 2. System-level Tesseract OCR

Tesseract must be installed on your OS:

**Ubuntu / Debian:**
```bash
sudo apt-get update && sudo apt-get install -y tesseract-ocr poppler-utils
```

**macOS (Homebrew):**
```bash
brew install tesseract poppler
```

**Windows:**
- Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
- Add the install directory to your `PATH` (e.g. `C:\Program Files\Tesseract-OCR`)
- Also install Poppler for Windows: https://github.com/oschwartz10612/poppler-windows/releases

### 3. Python dependencies

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python agent.py --input <input_folder> --output <output_folder>
```

**Example:**
```bash
python agent.py --input input_docs --output results
```

This will:
1. Process every `.pdf` and `.txt` file in `input_docs/`
2. Write one `<filename>_result.json` per file into `results/`
3. Write a combined `results/summary.json`

**Short flags also work:**
```bash
python agent.py -i input_docs -o results
```

---

## Output Format

Each result file is a JSON object:

```json
{
  "file": "claim_001.pdf",
  "extractedFields": {
    "policy_number": "POL-123456",
    "policyholder_name": "Jane Smith",
    "incident_date": "03/10/2026",
    "incident_time": "14:30",
    "incident_location": "123 Main St, Springfield, IL, USA",
    "incident_description": "Rear-ended at traffic signal.",
    "claimant_name": "Jane Smith",
    "claimant_contact": "9999999999",
    "claimant_email": "jane@example.com",
    "asset_type": "Automobile",
    "asset_description": "2021 Toyota Camry",
    "estimated_damage": "18000",
    "claim_type": "auto",
    "initial_estimate": "18000"
  },
  "missingFields": [
    "effective_date_from",
    "attachments"
  ],
  "recommendedRoute": "Manual Review",
  "reasoning": "Missing mandatory field(s): ['effective_date_from', 'attachments']. Human review needed to complete the claim."
}
```

### Routing values

| Value | Triggered when |
|-------|---------------|
| `"Fast-track"` | Estimated damage < ₹25,000 and no other flags |
| `"Manual Review"` | Any mandatory field is missing |
| `"Specialist Queue"` | Claim type is `injury` |
| `"Investigation Flag"` | Description contains: `fraud`, `inconsistent`, `staged`, `fabricated`, `suspicious`, `fake`, `misrepresent` |

> Priority order (highest first): **Investigation Flag > Specialist Queue > Manual Review > Fast-track**

---

## Running Tests

```bash
python -m unittest tests.test_agent -v
```

Expected output: **34 tests, 0 failures.**

The test suite covers:
- Field extraction from filled and empty text fixtures
- Claim type inference (auto, injury, theft, fire)
- Damage amount parsing edge cases
- All four routing rules
- JSON schema validation
- Integration tests against the actual sample PDF files

---

## Approach & Design Decisions

### Extraction Strategy
ACORD FNOL forms (like the provided samples) are complex multi-column PDFs where text often exists in both a text layer and as rendered image content. `pdfplumber` handles the text layer well but misses values typed into image-based form fields. To handle both:
- OCR is run via `pdf2image` + `pytesseract` on the first two pages (where FNOL data lives)
- A heuristic (`has_filled_content`) selects OCR output when it contains mixed-case text indicating real filled values

### Label Rejection (`clean()`)
A `clean()` helper filters out false positives — form section headers and field labels (e.g. `"PHONE (A/C, No, Ext):"`) that regex patterns can accidentally capture from blank forms.

### Routing Priority
The routing logic applies all rules and selects the highest-priority match, ensuring an injury claim with fraud language gets `Investigation Flag` (not just `Specialist Queue`).

---

## Adding More FNOL Documents

Drop any `.pdf` or `.txt` FNOL files into the `input_docs/` folder (or any folder you specify with `--input`) and re-run the agent. It processes all files in the folder automatically.
