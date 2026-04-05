cat > /home/claude/project/modules/validator.py << 'PYEOF'
"""
Validator / Rule Engine - compares form data vs extracted document data.
Flags mismatches and assigns a risk score.
"""
import re
from difflib import SequenceMatcher


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _normalize_date(d: str) -> str:
    """Normalize date to DD-MM-YYYY."""
    d = re.sub(r"[/\.]", "-", d.strip())
    return d


def validate(form_data: dict, extracted: dict) -> dict:
    """
    Compare form fields vs OCR-extracted fields.
    Returns a validation report with flags and overall risk.
    """
    flags = []
    passed = []

    # --- Name check ---
    form_name = form_data.get("name", "").strip()
    doc_name = extracted.get("name", "").strip()
    if form_name and doc_name:
        sim = _similarity(form_name, doc_name)
        if sim >= 0.85:
            passed.append({"field": "name", "form": form_name, "doc": doc_name, "note": "Match"})
        elif sim >= 0.6:
            flags.append({"field": "name", "form": form_name, "doc": doc_name,
                          "severity": "warning", "note": f"Partial match ({int(sim*100)}%)"})
        else:
            flags.append({"field": "name", "form": form_name, "doc": doc_name,
                          "severity": "error", "note": "Name mismatch"})
    elif not doc_name:
        flags.append({"field": "name", "severity": "warning", "note": "Name not found in document"})

    # --- DOB check ---
    form_dob = _normalize_date(form_data.get("dob", ""))
    doc_dob = _normalize_date(extracted.get("dob", ""))
    if form_dob and doc_dob:
        if form_dob == doc_dob:
            passed.append({"field": "dob", "form": form_dob, "doc": doc_dob, "note": "Match"})
        else:
            flags.append({"field": "dob", "form": form_dob, "doc": doc_dob,
                          "severity": "error", "note": "Date of Birth mismatch"})
    elif form_dob and not doc_dob:
        flags.append({"field": "dob", "severity": "warning", "note": "DOB not found in document"})

    # --- Aadhaar check ---
    form_aadhar = re.sub(r"\s", "", form_data.get("aadhaar", ""))
    doc_aadhar = re.sub(r"\s", "", extracted.get("aadhaar", ""))
    if form_aadhar and doc_aadhar:
        if form_aadhar == doc_aadhar:
            passed.append({"field": "aadhaar", "note": "Match"})
        else:
            flags.append({"field": "aadhaar", "form": form_aadhar, "doc": doc_aadhar,
                          "severity": "error", "note": "Aadhaar number mismatch"})

    # --- Risk score ---
    errors   = sum(1 for f in flags if f.get("severity") == "error")
    warnings = sum(1 for f in flags if f.get("severity") == "warning")
    risk = "high" if errors >= 2 else "medium" if errors == 1 or warnings >= 2 else "low"

    return {
        "flags":   flags,
        "passed":  passed,
        "risk":    risk,
        "summary": f"{errors} error(s), {warnings} warning(s)",
        "auto_approve": risk == "low" and errors == 0,
    }
PYEOF