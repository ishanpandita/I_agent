import argparse
import json
import os
import re
import sys
from pathlib import Path


# PDF TEXT EXTRACTION  (text layer + OCR fallback)

def extract_text_from_pdf(pdf_path: str) -> str:
    
    ocr_text   = _ocr_pdf(pdf_path)
    text_layer = ""

    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:

            pages_text = []
            for page in list(pdf.pages)[:2]:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            text_layer = "\n".join(pages_text)
    except Exception as e:
        print(f"  [warn] pdfplumber failed: {e}")

    def has_filled_content(txt: str) -> bool:
        """Heuristic: text has lowercase words or email-like patterns → filled form."""
        lower_words = re.findall(r'[a-z]{3,}', txt)
        return len(lower_words) > 3

    if ocr_text and has_filled_content(ocr_text):
        return ocr_text
    if text_layer and has_filled_content(text_layer):
        return text_layer
    return ocr_text if len(ocr_text) >= len(text_layer) else text_layer


def _ocr_pdf(pdf_path: str) -> str:
    """Convert each PDF page to image and run Tesseract OCR."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
        pages = convert_from_path(pdf_path, dpi=200)
        parts = []
        for page_img in pages[:2]:  # only first 2 pages for FNOL data
            parts.append(pytesseract.image_to_string(page_img))
        return "\n".join(parts)
    except Exception as e:
        print(f"  [warn] OCR failed: {e}")
        return ""


# FIELD EXTRACTION

# using Regex 
def _find(pattern: str, text: str, flags=re.IGNORECASE) -> str:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else ""


def extract_fields(text: str) -> dict:

    t = text

    fields = {}

    def clean(val: str) -> str | None:
        if not val:
            return None
        val = val.strip()
        if len(val) < 2:
            return None

        if re.match(r'^[\d\s\-,\.]+$', val):
            return val
        
        if re.match(r'^[A-Z\s\(\)/,\.\-:]+$', val) and len(val) < 60:
            return None
        
        if re.match(r'^[A-Z][A-Z\s]+\s*\([A-Za-z/,\.\s]+\)\s*:?\s*$', val):
            return None
        
        if val.endswith(':') and re.match(r'^[A-Z\s\(\)/,\.]+', val) and len(val) < 40:
            return None
        return val

    fields["policy_number"] = (
        clean(_find(r"POLICY\s*NUMBER\s*\n\s*(\d{5,20})", t))
        or clean(_find(r"POLICY\s*NUMBER[:\s]+(\d{5,20})", t))
        or clean(_find(r"\b(POL[-\s]?\d{5,})\b", t))
        or clean(_find(r"^CONTACT\s+(\d{8,13})\s*$", t, re.MULTILINE))
        or clean(_find(r"CONTACT\s+(\d{8,13})\b", t))
    )

    name_match = re.search(r"NAME\s+OF\s+INSURED[^\n]*\n\s*([^\n]{2,60})", t, re.IGNORECASE)
    if name_match:
        candidate = name_match.group(1).strip()

        if re.search(r"MARITAL|FEIN|appli|STATUS|MAILING", candidate, re.IGNORECASE):
            candidate = None
        fields["policyholder_name"] = clean(candidate)
    else:
        fields["policyholder_name"] = None


    fields["incident_date"] = (
        _find(r"DATE\s+OF\s+LOSS\s+AND\s+TIME[^\n]*\n\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", t)
        or _find(r"DATE\s+OF\s+LOSS\s+AND\s+TIME[^\n]*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", t)
        or _find(r"(\d{1,2}/\d{1,2}/\d{4})", t) 
    ) or None

    # TIME OF LOSS
    fields["incident_time"] = (
        _find(r"DATE\s+OF\s+LOSS\s+AND\s+TIME[^\n]*\n\s*\S+\s+(\d{1,2}:\d{2}\s*(?:AM|PM)?)", t, re.IGNORECASE)
        or _find(r"(\d{1,2}:\d{2}\s*(?:AM|PM))", t, re.IGNORECASE)
    ) or None

    # LOCATION OF LOSS 
    loc_main = ""
    loc_match = re.search(r"LOCATION\s+OF\s*LOSS[^\n]*\n\s*([^\n]{3,80})", t, re.IGNORECASE)
    if loc_match:
        candidate = loc_match.group(1).strip()
        if not re.match(r'^[A-Z\s\(\)/,\.\-:]+$', candidate):
            loc_main = candidate
    loc_street  = clean(_find(r"STREET\s*:\s*([^\n]{3,80})", t)) or ""
    loc_city    = clean(_find(r"CITY[,\s]+STATE[,\s]+ZIP\s*:\s*([^\n]{3,60})", t)) or ""
    loc_country = clean(_find(r"COUNTRY\s*:\s*([^\n]{2,30})", t)) or ""
    loc_parts   = []
    for part in [loc_main, loc_street, loc_city, loc_country]:
        if part and part not in " ".join(loc_parts):
            loc_parts.append(part)
    fields["incident_location"] = ", ".join(loc_parts) if loc_parts else None

    # DESCRIPTION OF ACCIDENT 
    desc_raw = (
        _find(
            r"DESCRIPTION\s+OF\s+ACCIDENT[^\n]*\n([\s\S]{5,600}?)"
            r"(?=\n\s*(?:INSURED\s+VEHICLE|INJURED|WITNESSES|Page\s+\d|ACORD\s+\d))",
            t, re.IGNORECASE
        )
        or _find(r"DESCRIPTION\s+OF\s+ACCIDENT[^\n]*\n([^\n]{5,300})", t, re.IGNORECASE)
    )
    if desc_raw:
        lines = [l.strip() for l in desc_raw.split('\n') if l.strip()]
        content_lines = [
            l for l in lines
            if len(l) > 8 and not re.match(r'^[A-Z0-9\s\(\)/,\.\-:]+$', l)
        ]
        fields["incident_description"] = " ".join(content_lines).strip() if content_lines else None
    else:
        fields["incident_description"] = None


    fields["claimant_name"] = fields["policyholder_name"]

    fields["claimant_contact"] = (
        _find(r"PRIMARY\s+PHONE\s*#[^\n]*\n\s*(\d{7,15})", t)
        or _find(r"DATE\s+OF\s+BIRTH[^\n]*\n\s*[\d/]+\s*\n\s*(\d{7,15})", t)
        or _find(r"\b(\d{10})\b", t)
    ) or None

    # CLAIMANT EMAIL
    fields["claimant_email"] = (
        _find(r"E[-\s]?MAIL\s*ADDRESS[:\s]+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", t)
        or _find(r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", t)
    ) or None

    # THIRD PARTY NAME — OWNER'S NAME AND ADDRESS in OTHER VEHICLE section (page 2)
    owner_matches = list(re.finditer(
        r"OWNER'?S?\s+NAME\s+AND\s+ADDRESS[^\n]*\n\s*([^\n]{3,60})", t, re.IGNORECASE
    ))
    if len(owner_matches) >= 2:
        fields["third_party_name"] = clean(owner_matches[1].group(1))
    else:
        fields["third_party_name"] = None

    other_sec = _find(
        r"OTHER\s+VEHICLE[^\n]*\n([\s\S]{0,500}?)(?:\nREMARKS|\nINJURED|\Z)",
        t, re.IGNORECASE
    )
    fields["third_party_contact"] = (
        _find(r"\b(\d{10})\b", other_sec) if other_sec else None
    ) or None


    fields["asset_type"] = "Automobile"

    veh_num   = clean(_find(r"[Vv][Ee][Hh]\s*#\s*([A-Za-z0-9]+)\s+(?:YEAR|\d{4})", t)) or \
                clean(_find(r"[Vv][Ee][Hh]\s*#\s+([A-Za-z0-9]{2,15})\b", t)) or ""
    year_val  = _find(r"YEAR\s*[:\s]\s*(\d{4})\b", t) or ""
    make_val  = clean(_find(r"MAKE\s*:\s*([A-Za-z][A-Za-z0-9\s]{1,19}?)(?:\s+BODY|\s+PLATE|\s*\n)", t)) or ""
    model_val = clean(_find(r"MODEL\s*:\s*([A-Za-z0-9\s]{2,20}?)(?:\s+V\.?I\.?N|\s*\n)", t)) or ""
    veh_parts = [x for x in [veh_num, year_val, make_val, model_val] if x and len(x) > 1]
    fields["asset_description"] = " ".join(veh_parts).strip() or None

    fields["asset_id_vin"] = _find(r"V\.?I\.?N\.?[:\s]+([A-HJ-NPR-Z0-9]{5,17})", t) or None

    # PLATE NUMBER
    fields["asset_plate"] = clean(_find(r"PLATE\s+NUMBER[:\s]+([A-Z0-9\-]{3,15})", t)) or None

    # ESTIMATE AMOUNT — numeric field at bottom of INSURED VEHICLE section
    raw_est = (
        _find(r"ESTIMATE\s+AMOUNT\s*[:\s]*([\d,\.]+)", t)
        or _find(r"ESTIMATED?\s+DAMAGE\s*[:\s]*([\d,\.]+)", t)
        or _find(r"\$\s*([\d,]+(?:\.\d{2})?)", t)
    )
    fields["estimated_damage"] = raw_est.strip() if raw_est else None
    fields["initial_estimate"] = fields["estimated_damage"]


    fields["report_number"] = clean(_find(r"REPORT\s+NUMBER[:\s]+([^\n]{3,30})", t)) or None

    return fields


def _infer_claim_type(text: str) -> str | None:
    
    legal_start = re.search(r"Applicable in Alabama", text, re.IGNORECASE)
    snippet = text[:legal_start.start()] if legal_start else text

    desc_match = re.search(
        r"DESCRIPTION\s+OF\s+ACCIDENT[^\n]*\n([\s\S]{0,600}?)(?:\n\s*(?:INSURED\s+VEHICLE|INJURED\n|WITNESSES)|\Z)",
        snippet, re.IGNORECASE
    )
    desc_section = desc_match.group(1) if desc_match else ""

    injury_pattern = re.compile(
        r"\b(?:injuries|injured\s+\w|bodily\s+injur|personal\s+injur|sustained\s+injur|serious\s+injur)\b",
        re.IGNORECASE
    )
    if injury_pattern.search(desc_section) or injury_pattern.search(snippet):
        return "injury"

    for scope in [desc_section, snippet]:
        if re.search(r"\bTHEFT\b|\bSTOLEN\b", scope, re.IGNORECASE):
            return "theft"
        if re.search(r"\bFIRE\b|\bBURN\b", scope, re.IGNORECASE):
            return "fire"
        if re.search(r"\bFLOOD\b|\bWATER\s+DAMAGE\b", scope, re.IGNORECASE):
            return "flood"

    if re.search(r"\bAUTOMOBILE\s+LOSS\b|\bAUTO\b|\bCAR\b|\bVEHICLE\b", snippet, re.IGNORECASE):
        return "auto"
    return None


# All fields
MANDATORY_FIELDS = [
    "policy_number",
    "policyholder_name",
    "incident_date",
    "incident_time",
    "incident_location",
    "incident_description",
    "claimant_name",
    "claimant_contact",
    "asset_type",
    "estimated_damage",
    "initial_estimate",
]


def find_missing_fields(fields: dict) -> list:
    missing = []
    for f in MANDATORY_FIELDS:
        val = fields.get(f)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            missing.append(f)
    return missing


FRAUD_KEYWORDS = ["fraud", "inconsistent", "staged", "fabricated", "fake",
                  "suspicious", "misrepresent"]

DAMAGE_THRESHOLD = 25_000


def _parse_damage_amount(val: str | None) -> float | None:
    if not val:
        return None
    cleaned = re.sub(r"[^\d.]", "", val.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def determine_route(fields: dict, missing: list) -> tuple[str, str]:
   
    reasons = []
    route = None

    description = (fields.get("incident_description") or "").lower()
    damage_str  = fields.get("estimated_damage")
    claim_type  = (fields.get("claim_type") or "").lower()
    damage_amt  = _parse_damage_amount(damage_str)

    # Rule 1: Fraud keywords → Investigation Flag
    flagged_words = [kw for kw in FRAUD_KEYWORDS if kw in description]
    if flagged_words:
        route = "Investigation Flag"
        reasons.append(
            f"Incident description contains suspicious keyword(s): {flagged_words}."
        )

    # Rule 2: Injury claim → Specialist Queue
    if claim_type == "injury":
        if route is None:
            route = "Specialist Queue"
        reasons.append("Claim type is 'injury'; requires specialist handling.")

    # Rule 3: Missing mandatory fields → Manual Review
    if missing:
        if route is None:
            route = "Manual Review"
        reasons.append(
            f"Missing mandatory field(s): {missing}. Human review needed to complete the claim."
        )

    # Rule 4: Low damage → Fast-track
    if damage_amt is not None and damage_amt < DAMAGE_THRESHOLD:
        if route is None:
            route = "Fast-track"
        reasons.append(
            f"Estimated damage ({damage_str}) is below ₹{DAMAGE_THRESHOLD:,}; eligible for fast-track processing."
        )

    # Fallback
    if route is None:
        if damage_amt is None:
            route = "Manual Review"
            reasons.append("Damage amount could not be determined; defaulting to manual review.")
        else:
            route = "Manual Review"
            reasons.append(
                f"Estimated damage ({damage_str}) is ₹{damage_amt:,.0f} which meets or exceeds "
                f"₹{DAMAGE_THRESHOLD:,} threshold; standard manual review."
            )

    return route, " ".join(reasons)



def process_file(pdf_path: str) -> dict:
    print(f"  Processing: {os.path.basename(pdf_path)}")

    text = extract_text_from_pdf(pdf_path)
    if not text.strip():
        return {
            "file": os.path.basename(pdf_path),
            "error": "Could not extract any text from document.",
            "extractedFields": {},
            "missingFields": list(MANDATORY_FIELDS),
            "recommendedRoute": "Manual Review",
            "reasoning": "No text could be extracted from this document. Full manual review required."
        }

    fields   = extract_fields(text)
    missing  = find_missing_fields(fields)
    route, reasoning = determine_route(fields, missing)

    extracted_clean = {k: v for k, v in fields.items() if v is not None}

    return {
        "file": os.path.basename(pdf_path),
        "extractedFields": extracted_clean,
        "missingFields": missing,
        "recommendedRoute": route,
        "reasoning": reasoning
    }


def process_folder(input_folder: str, output_folder: str):
    input_path  = Path(input_folder)
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(input_path.glob("*.pdf")) + sorted(input_path.glob("*.txt"))
    if not pdf_files:
        print(f"No PDF/TXT files found in '{input_folder}'.")
        sys.exit(1)

    all_results = []
    for pdf_file in pdf_files:
        result = process_file(str(pdf_file))
        all_results.append(result)

        # Individual output file
        out_name = pdf_file.stem + "_result.json"
        out_file = output_path / out_name
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"  → Saved: {out_file}")

def main():
    parser = argparse.ArgumentParser(
        description="FNOL Autonomous Insurance Claims Processing Agent"
    )
    parser.add_argument("--input",  "-i", required=True,  help="Input folder containing FNOL PDF/TXT files")
    parser.add_argument("--output", "-o", required=True,  help="Output folder for JSON results")
    args = parser.parse_args()

    print(f"\n{'='*55}")
    print("  Ishan Agent ")
    print(f"{'='*55}")
    print(f"  Input  : {args.input}")
    print(f"  Output : {args.output}")
    print(f"{'='*55}\n")

    process_folder(args.input, args.output)


if __name__ == "__main__":
    main()
