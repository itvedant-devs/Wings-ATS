import hashlib
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.datastructures import FileStorage
from flask_sqlalchemy import SQLAlchemy
import os, json, re
import pymysql   # 👈 Add this
pymysql.install_as_MySQLdb()  # 👈 And 
from config import Config
from models import db, Meta,User # your existing table model
from utils import (
    extract_text_from_file,
    validate_resume_content,
)
from analysis import perform_structured_analysis
from groq_client import client, get_groq_response, nlp_model



# --- Helper Function: PHP-like uniqid(true) ---
def uniqid(prefix="", more_entropy=False):
    """Mimic PHP's uniqid(true) using time-based microseconds"""
    mtime = time.time()  # current time (float seconds)
    uniq = f"{prefix}{int(mtime * 1000):x}"  # microseconds → hex string
    # if more_entropy:
    #     uniq += f"{hashlib.md5(str(mtime).encode()).hexdigest()[:8]}"
    return uniq


# --- Flask App Setup ---
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db.init_app(app)

with app.app_context():
    db.create_all()


# --- API Endpoint ---
@app.route('/analyze_resume', methods=['POST'])
def analyze_resume():
    # --- Get user_id (mandatory) ---
    user_id_str = request.form.get("user_id")
    if not user_id_str:
        return jsonify({"error": "No user_id provided"}), 400

    try:
        user_id = int(user_id_str)
    except ValueError:
        return jsonify({"error": "Invalid user_id, must be an integer"}), 400

    # --- Get resume file (mandatory) ---
    if 'resume' not in request.files:
        return jsonify({"error": "No resume file provided"}), 400

    resume_file = request.files['resume']
    if not resume_file.filename:
        return jsonify({"error": "No selected file"}), 400

    # Optional: get job role and description if provided
    target_job_role = request.form.get('target_job_role', '').strip()
    job_description = request.form.get('job_description', '').strip()

    # --- Extract and normalize resume text ---
    file_text = extract_text_from_file(resume_file)
    if not file_text:
        return jsonify({"error": "Failed to extract text from resume"}), 500

    normalized_text = re.sub(r"\s+", " ", file_text.strip().lower())


    # ✅ Fetch user's first name from DB
    user = User.query.filter_by(id=user_id).first()
    first_name = ""
    if user and user.first_name:
        first_name = re.sub(r"\s+", "", user.first_name).lower()

    # ✅ Generate encrypted/unique resume file name
    # Get file extension safely
    _, file_extension = os.path.splitext(resume_file.filename)
    file_extension = file_extension.lstrip('.')  # remove leading dot
    unique_id = uniqid(more_entropy=True)
    encrypted_filename = f"{first_name}_{unique_id}_{user_id}.{file_extension}" if first_name else f"{unique_id}{user_id}.{file_extension}"


    # --- Check if record exists for user ---
    existing_entry = Meta.query.filter_by(
        key=user_id, type="users", sub_type="resume_analysis_results"
    ).first()

    existing_value = []
    if existing_entry:
        try:
            existing_value = json.loads(existing_entry.value)
        except Exception:
            existing_value = []

        # ✅ Check if same resume already exists
        for i, record in enumerate(existing_value):
            if record.get("normalized_text") == normalized_text:

                # --- Move this record to the end (latest position) ---
                existing_value.append(existing_value.pop(i))

                # --- Update DB (reorder queue) ---
                existing_entry.value = json.dumps(existing_value, ensure_ascii=False)
                db.session.commit()

                
                # Return stored score & analysis, DO NOT push duplicate
                return jsonify({
                    "backend_message": "This resume has already been analyzed (same content).",
                    "analysis_results": record.get("analysis_results"),
                    "structured_findings": record.get("structured_findings"),
                    "score": record.get("score"),
                    "quick_fixes": record.get("quick_fixes"),
                    "encrypted_file_name": record.get("encrypted_file_name"),  # ✅ include here
                    "total_stored": len(existing_value)
                })

    # --- Validate resume ---
    is_valid, validation_message = validate_resume_content(file_text)
    if not is_valid:
        return jsonify({"error": validation_message}), 400

    if not nlp_model:
        return jsonify({"error": "NLP model not loaded"}), 500

    # --- Structured analysis ---
    structured_findings = perform_structured_analysis(file_text, job_description, nlp_model, target_job_role)

    # --- Get prompt template ---
    analysis_prompt_path = os.path.join(os.path.dirname(__file__), "analysis_prompt.txt")
    try:
        with open(analysis_prompt_path, encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        prompt_template = "You are an expert ATS and career advisor..."

    # --- Get AI response ---
    response_content = get_groq_response(file_text, job_description, prompt_template, structured_findings, target_job_role)

    try:
        response_json = json.loads(response_content)
    except json.JSONDecodeError:
        response_json = {"score": 0, "quick_fixes": [], "raw_text": response_content}

    # --- Build JSON payload ---
    response_payload = {
        "normalized_text": normalized_text,
        "analysis_results": response_content,
        "structured_findings": structured_findings,
        "file_name": resume_file.filename,
        "encrypted_file_name": encrypted_filename,  # ✅ new field
        "score": response_json.get("score", 0),
        "quick_fixes": response_json.get("quick_fixes", [])
    }

    # --- Append new record and maintain max 10 (FIFO) ---
    existing_value.append(response_payload)
    if len(existing_value) > 10:
        existing_value = existing_value[-10:]  # keep only latest 10

    # --- Save to DB ---
    if existing_entry:
        existing_entry.value = json.dumps(existing_value, ensure_ascii=False)
    else:
        new_entry = Meta(
            key=user_id,
            value=json.dumps(existing_value, ensure_ascii=False),
            type="users",
            sub_type="resume_analysis_results"
        )
        db.session.add(new_entry)

    db.session.commit()
    

    # --- Return latest analysis result ---
    return jsonify({
        "backend_message": "New resume analyzed successfully.",
        "analysis_results": response_content,
        "structured_findings": structured_findings,
        "score": response_json.get("score", 0),
        "quick_fixes": response_json.get("quick_fixes", []),
        "total_stored": len(existing_value),
        "encrypted_file_name": encrypted_filename  # ✅ included in response

    })


if __name__ == '__main__':
    app.run(debug=True, port=5001)



