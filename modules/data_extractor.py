cat > /home/claude/project/modules/data_extractor.py << 'PYEOF'
"""
Data Extractor - parses structured fields from raw OCR text.
"""
import re


PATTERNS = {
    "name": [
        r"Name[:\s]+([A-Za-z\s\.]+)",
        r"Applicant[:\s]+([A-Za-z\s\.]+)",
    ],
    "dob": [
        r"Date of Birth[:\s]+([\d\-/\.]+)",
        r"DOB[:\s]+([\d\-/\.]+)",
        r"D\.O\.B[:\s]+([\d\-/\.]+)",
    ],
    "address": [
        r"Address[:\s]+(.+?)(?:\n|Aadhaar|Community|$)",
    ],
    "aadhaar": [
        r"Aadhaar[:\s]+([\d\s]{12,16})",
        r"Aadhar[:\s]+([\d\s]{12,16})",
    ],
    "community": [
        r"Community[:\s]+([A-Za-z/\s]+)",
        r"Caste[:\s]+([A-Za-z/\s]+)",
    ],
    "income": [
        r"Income[:\s]+Rs\.?\s*([\d,]+)",
        r"Annual Income[:\s]+Rs\.?\s*([\d,]+)",
    ],
}


def extract_fields(raw_text: str) -> dict:
    """Extract key fields from OCR text using regex patterns."""
    extracted = {}

    for field, patterns in PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip().strip(",").strip()
                # Trim excessively long matches
                if len(value) > 100:
                    value = value[:100]
                extracted[field] = value
                break

    return extracted
PYEOF