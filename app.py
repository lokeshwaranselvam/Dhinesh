cat > /home/claude/project/app.py << 'PYEOF'
"""
e-Sevai Intelligent Middleware - Main Flask Application
"""
import json
import os
from datetime import datetime, timezone

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from werkzeug.utils import secure_filename

from config import Config
from utils.helpers import generate_id, allowed_file, timestamp_now, ensure_dirs
from modules.ocr_engine import extract_text_from_file
from modules.data_extractor import extract_fields
from modules.validator import validate
from modules.sla_engine import start_sla_timer, check_sla, complete_sla_step
from modules.audit_logger import append_audit, get_audit_trail, verify_chain_integrity

app = Flask(__name__)
app.config.from_object(Config)

ensure_dirs(
    app.config["UPLOAD_FOLDER"],
    app.config["EXTRACTED_FOLDER"],
    os.path.dirname(app.config["DB_PATH"]),
)


# ── DB helpers ──────────────────────────────────────────────────────────────

def load_db():
    path = app.config["DB_PATH"]
    if not os.path.exists(path):
        return {"applications": {}, "audit_chain": []}
    with open(path) as f:
        return json.load(f)


def save_db(data):
    with open(app.config["DB_PATH"], "w") as f:
        json.dump(data, f, indent=2)


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    db = load_db()
    apps = list(db["applications"].values())
    apps.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
    stats = {
        "total": len(apps),
        "pending": sum(1 for a in apps if "Pending" in a.get("status", "")),
        "approved": sum(1 for a in apps if a.get("status") == "Approved"),
        "flagged": sum(1 for a in apps if a.get("risk") in ("high", "medium")),
        "delayed": sum(1 for a in apps if "Delayed" in a.get("status", "")),
    }
    return render_template("index.html", applications=apps, stats=stats, services=Config.SERVICES)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html", services=Config.SERVICES)

    # Form fields
    form_data = {
        "name":    request.form.get("name", "").strip(),
        "dob":     request.form.get("dob", "").strip(),
        "aadhaar": request.form.get("aadhaar", "").strip(),
        "service": request.form.get("service", "").strip(),
        "address": request.form.get("address", "").strip(),
    }

    file = request.files.get("document")
    if not file or file.filename == "":
        flash("Please upload a document.", "error")
        return redirect(url_for("upload"))

    if not allowed_file(file.filename, app.config["ALLOWED_EXTENSIONS"]):
        flash("Invalid file type. Allowed: PDF, PNG, JPG, JPEG", "error")
        return redirect(url_for("upload"))

    # Save file
    app_id = generate_id()
    filename = secure_filename(f"{app_id}_{file.filename}")
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # OCR
    raw_text = extract_text_from_file(filepath)
    extracted = extract_fields(raw_text)

    # Validate
    report = validate(form_data, extracted)

    # Save extracted data
    ext_path = os.path.join(app.config["EXTRACTED_FOLDER"], f"{app_id}.json")
    with open(ext_path, "w") as f:
        json.dump({"raw_text": raw_text, "extracted": extracted}, f, indent=2)

    # Determine status
    if report["auto_approve"]:
        status = "Auto-Approved"
    elif report["risk"] == "high":
        status = "Pending Officer Review (High Risk)"
    else:
        status = "Pending Officer Review"

    # Build application record
    application = {
        "id":           app_id,
        "service":      form_data["service"],
        "form_data":    form_data,
        "extracted":    extracted,
        "validation":   report,
        "risk":         report["risk"],
        "status":       status,
        "submitted_at": timestamp_now(),
        "filename":     filename,
        "sla":          {},
    }

    db = load_db()
    db["applications"][app_id] = application
    save_db(db)

    # Audit
    append_audit(app.config["DB_PATH"], app_id, "citizen", "submitted",
                 {"service": form_data["service"], "filename": filename})
    append_audit(app.config["DB_PATH"], app_id, "system", "ocr_complete",
                 {"fields_extracted": list(extracted.keys())})
    append_audit(app.config["DB_PATH"], app_id, "system", "validation_complete",
                 {"risk": report["risk"], "summary": report["summary"]})

    # Start SLA
    start_sla_timer(app.config["DB_PATH"], app_id, "officer_review",
                    app.config["SLA_LIMITS"]["officer_review"])

    return redirect(url_for("result", app_id=app_id))


@app.route("/result/<app_id>")
def result(app_id):
    db = load_db()
    application = db["applications"].get(app_id)
    if not application:
        flash("Application not found.", "error")
        return redirect(url_for("index"))
    audit = get_audit_trail(app.config["DB_PATH"], app_id)
    sla = check_sla(app.config["DB_PATH"], app_id, "officer_review")
    return render_template("result.html", app=application, audit=audit, sla=sla)


@app.route("/officer/<app_id>", methods=["POST"])
def officer_action(app_id):
    db = load_db()
    application = db["applications"].get(app_id)
    if not application:
        return jsonify({"error": "Not found"}), 404

    action = request.form.get("action")
    reason = request.form.get("reason", "")
    officer = request.form.get("officer", "Officer")

    if action == "approve":
        application["status"] = "Approved"
        complete_sla_step(app.config["DB_PATH"], app_id, "officer_review")
    elif action == "reject":
        application["status"] = "Rejected"
        complete_sla_step(app.config["DB_PATH"], app_id, "officer_review")
    elif action == "escalate":
        application["status"] = "Escalated to Senior Officer"

    db["applications"][app_id] = application
    save_db(db)

    append_audit(app.config["DB_PATH"], app_id, officer, action,
                 {"reason": reason, "new_status": application["status"]})

    return redirect(url_for("result", app_id=app_id))


@app.route("/api/applications")
def api_applications():
    db = load_db()
    return jsonify(list(db["applications"].values()))


@app.route("/api/audit/<app_id>")
def api_audit(app_id):
    trail = get_audit_trail(app.config["DB_PATH"], app_id)
    return jsonify(trail)


@app.route("/api/chain/verify")
def api_verify_chain():
    ok, msg = verify_chain_integrity(app.config["DB_PATH"])
    return jsonify({"valid": ok, "message": msg})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
PYEOF