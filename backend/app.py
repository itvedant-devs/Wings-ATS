import hashlib
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.datastructures import FileStorage
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os, json, re
import pymysql
pymysql.install_as_MySQLdb()
from config import Config
from models import db, Meta, User
from utils import (
    extract_text_from_file,
    validate_resume_content,
)
from analysis import perform_structured_analysis
from groq_client import client, get_groq_response, nlp_model

def _normalize_record(record):
    if isinstance(record, dict):
        return record
    if isinstance(record, str):
        try:
            decoded = json.loads(record)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
    return None

def uniqid(prefix="", more_entropy=False):
    mtime = time.time()
    uniq = f"{prefix}{int(mtime * 1000):x}"
    return uniq

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/analyze_resume', methods=['POST'])
def analyze_resume():
    # 1. Input Validation
    user_id_str = request.form.get("user_id")
    if not user_id_str:
        return jsonify({"error": "No user_id provided"}), 400

    try:
        user_id = int(user_id_str)
    except ValueError:
        return jsonify({"error": "Invalid user_id, must be an integer"}), 400

    if 'resume' not in request.files:
        return jsonify({"error": "No resume file provided"}), 400

    resume_file = request.files['resume']
    if not resume_file.filename:
        return jsonify({"error": "No selected file"}), 400
    
    # 2. File Size Calculation
    resume_file.seek(0, os.SEEK_END)
    file_size_bytes = resume_file.tell()
    resume_file.seek(0)
    file_size = round(file_size_bytes / 1024, 2)

    target_job_role = request.form.get('target_job_role', '').strip()
    job_description = request.form.get('job_description', '').strip()

    # 3. Text Extraction
    file_text = extract_text_from_file(resume_file)
    
    # UPDATED: Check for empty text and provide specific "Scanned PDF" feedback
    if not file_text or not file_text.strip():
        return jsonify({
            "error": "We could not read any text from this file. It may be a scanned image or protected. Please upload a standard text-selectable PDF or DOCX file."
        }), 400

    normalized_text = re.sub(r"\s+", " ", file_text.strip().lower())
    resume_hash = hashlib.sha256(normalized_text.encode()).hexdigest()

    # 4. Fetch User Name (Priority: POST Params > DB Lookup)
    req_first_name = request.form.get("first_name", "").strip()
    req_last_name = request.form.get("last_name", "").strip()
    
    raw_first = ""
    raw_last = ""

    if req_first_name or req_last_name:
        # Case A: PHP sent the names directly
        raw_first = req_first_name
        raw_last = req_last_name
        print(f"DEBUG: Received names from POST request: {raw_first} {raw_last}")
    else:
        # Case B: Names missing in POST, fallback to Database
        try:
            print(f"DEBUG: Names not in POST, querying DB for user_id: {user_id}")
            # Check if we can use the ORM directly (cleaner)
            user = User.query.filter_by(id=user_id).first()
            if user:
                raw_first = str(user.first_name) if user.first_name else ""
                raw_last = str(user.last_name) if user.last_name else ""
            else:
                # Fallback to raw SQL if ORM fails or for redundancy
                sql = text("SELECT first_name, last_name FROM users WHERE id = :uid")
                result = db.session.execute(sql, {'uid': user_id}).fetchone()
                if result:
                    raw_first = str(result[0]) if result[0] else ""
                    raw_last = str(result[1]) if result[1] else ""
                    
        except Exception as e:
            print(f"Error fetching user name: {e}")

    # Create formatted name string for response
    user_full_name = f"{raw_first} {raw_last}".strip()
    if not user_full_name:
        user_full_name = "Unknown User"

    # 5. Filename Encryption
    f_clean = re.sub(r'[^a-zA-Z0-9]', '', raw_first).upper()
    l_clean = re.sub(r'[^a-zA-Z0-9]', '', raw_last).upper()

    if not f_clean: 
        f_clean = "USER"
    if not l_clean: 
        l_clean = "CANDIDATE"

    _, file_extension = os.path.splitext(resume_file.filename)
    file_extension = file_extension.lstrip('.')
    unique_id = uniqid(more_entropy=True)
    
    encrypted_filename = f"{f_clean}_{l_clean}_{unique_id}_{user_id}.{file_extension}"

    # 6. Check Local Duplicates
    existing_entry = Meta.query.filter_by(key=user_id, type="users").first()
    existing_value = []
    
    if existing_entry:
        try:
            existing_value = json.loads(existing_entry.value)
        except Exception:
            existing_value = []

        for i, record in enumerate(existing_value):
            rec_dict = _normalize_record(record)
            if not rec_dict:
                continue
            if rec_dict.get("resume_hash") == resume_hash:
                return jsonify({
                    "resume_hash": resume_hash,
                    "duplicate": True,
                    "backend_message": "This resume has already been analyzed (same content).",
                    "score": rec_dict.get("score"),
                    "quick_fixes": rec_dict.get("quick_fixes"),
                    "file_name": resume_file.filename,
                    # OVERRIDE: Return current uploaded filename instead of stored encrypted name
                    "encrypted_file_name": resume_file.filename,
                    "total_stored": len(existing_value),
                    "file_size": file_size,
                    "user_name": user_full_name,
                    "first_name": raw_first,
                    "last_name": raw_last,
                    "user_id": user_id
                })

    # 7. Check Global Duplicates
    all_entries = Meta.query.filter_by(type="users").all()
    for entry in all_entries:
        try:
            value_list = json.loads(entry.value)
        except Exception:
            continue
        for idx, rec in enumerate(value_list):
            rec_dict = _normalize_record(rec)
            if not rec_dict:
                continue
            stored_hash = rec_dict.get("resume_hash") 
            if stored_hash and stored_hash == resume_hash:
                return jsonify({
                    "resume_hash": resume_hash,
                    "duplicate": True,
                    "global_duplicate": True,
                    "message": "This resume has already been analyzed globally.",
                    "score": rec_dict.get("score"),
                    "quick_fixes": rec_dict.get("quick_fixes"),
                    "file_name": resume_file.filename,
                    # OVERRIDE: Return current uploaded filename instead of stored encrypted name
                    "encrypted_file_name": resume_file.filename,
                    "file_size": file_size,
                    "user_name": user_full_name,
                    "first_name": raw_first,
                    "last_name": raw_last,
                    "user_id": user_id
                })

    # 8. Validation
    is_valid, validation_message = validate_resume_content(normalized_text)
    if not is_valid:
        return jsonify({"error": validation_message}), 400

    if not nlp_model:
        return jsonify({"error": "NLP model not loaded"}), 500

    # 9. Analysis
    structured_findings = perform_structured_analysis(file_text, job_description, nlp_model, target_job_role)

    analysis_prompt_path = os.path.join(os.path.dirname(__file__), "analysis_prompt.txt")
    try:
        with open(analysis_prompt_path, encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        prompt_template = "You are an expert ATS and career advisor..."

    response_content = get_groq_response(file_text, job_description, prompt_template, structured_findings, target_job_role)

    try:
        response_json = json.loads(response_content)
    except json.JSONDecodeError:
        response_json = {"score": 0, "quick_fixes": [], "raw_text": response_content}

    new_record = {
        "resume_hash": resume_hash,
        "score": response_json.get("score", 0),
        "quick_fixes": response_json.get("quick_fixes", []),
        "file_name": resume_file.filename,
        "encrypted_file_name": encrypted_filename,
        "file_size": file_size,
        "timestamp": time.time(),
        "analysis_results": response_content
    }

    # 10. Save to DB
    existing_value.append(new_record)

    if existing_entry:
        existing_entry.value = json.dumps(existing_value)
    else:
        new_entry = Meta(key=user_id, type="users", value=json.dumps(existing_value))
        db.session.add(new_entry)

    db.session.commit()

    # 11. Final Success Response
    return jsonify({
        "normalized_text" : normalized_text, 
        "duplicate": False,
        "backend_message": "New resume analyzed successfully.",
        "analysis_results": response_content,
        "score": response_json.get("score", 0),
        "quick_fixes": response_json.get("quick_fixes", []),
        "total_stored": len(existing_value),
        "file_name": resume_file.filename,
        "encrypted_file_name": encrypted_filename,
        "file_size": file_size,
        "resume_hash": resume_hash,
        "user_name": user_full_name,
        "first_name": raw_first,
        "last_name": raw_last,
        "user_id": user_id
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)