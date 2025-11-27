
import hashlib
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.datastructures import FileStorage
from flask_sqlalchemy import SQLAlchemy
import os, json, re

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
    

    # --- Get file size ---
    # --- Get file size in MB ---
    resume_file.seek(0, os.SEEK_END)  # move cursor to end of file
    file_size_bytes = resume_file.tell()  # get file size in bytes
    resume_file.seek(0)  # reset cursor to start
    file_size = round(file_size_bytes / (1024 * 1024), 2)  # convert to MB (2 decimal places)



    # Optional: get job role and description if provided
    target_job_role = request.form.get('target_job_role', '').strip()
    job_description = request.form.get('job_description', '').strip()

    # --- Extract and normalize resume text ---
    file_text = extract_text_from_file(resume_file)
    if not file_text:
        return jsonify({"error": "We were unable to identify a resume in the uploaded file. Please ensure you have selected the correct document and upload it again."}), 500

    normalized_text = re.sub(r"\s+", " ", file_text.strip().lower())
    resume_hash = hashlib.sha256(normalized_text.encode()).hexdigest()



    #  Fetch user's first name from DB
    user = User.query.filter_by(id=user_id).first()
    first_name = ""
    # last_name = ""

    # if user and user.first_name and user.last_name:
    if user and user.first_name:
        first_name = re.sub(r"\s+", "", user.first_name).lower()
        # last_name = re.sub(r"\s+", "", user.last_name).lower()

    #  Generate encrypted/unique resume file name
    # Get file extension safely
    _, file_extension = os.path.splitext(resume_file.filename)
    file_extension = file_extension.lstrip('.')  # remove leading dot
    unique_id = uniqid(more_entropy=True)
    encrypted_filename = f"{first_name}_{unique_id}_{user_id}.{file_extension}" if first_name else f"{unique_id}{user_id}.{file_extension}"

    existing_entry = Meta.query.filter_by(key=user_id, type="users").first()


    existing_value = []
    if existing_entry:
        try:
            existing_value = json.loads(existing_entry.value)
        except Exception:
            existing_value = []

        #  Check if same resume already exists
        for i, record in enumerate(existing_value):
            if record.get("resume_hash") == resume_hash:
                
                return jsonify({
                    "resume_hash": resume_hash,
                    "duplicate": True,
                    "index": i,
                    "message": "This resume has already been analyzed (same content).",
                    "score": record.get("score"),
                    "quick_fixes": record.get("quick_fixes"),
                    "file_name": resume_file.filename,
                    "encrypted_file_name": record.get("encrypted_file_name"),  #  include here
                    "total_stored": len(existing_value),
                    "file_size": file_size  # Added field
                })


    # --------- validate global resume
    all_entries = Meta.query.filter_by(type="users").all()
    for entry in all_entries:
        try:
            value_list = json.loads(entry.value)
        except Exception:
            continue
        for idx, rec in enumerate(value_list):
            stored_hash = rec.get("resume_hash") 
            if stored_hash and stored_hash == resume_hash:
                # Found globally duplicate resume
                return jsonify({
                    "resume_hash": resume_hash,
                    "duplicate": True,
                    "global_duplicate": True,
                    "message": "This resume has already been analyzed globally.",
                    "score": rec.get("score"),
                    "quick_fixes": rec.get("quick_fixes"),
                    "file_name": resume_file.filename,
                    "encrypted_file_name": rec.get("encrypted_file_name"),
                    "file_size": file_size
                })


    # --- Validate resume ---
    # is_valid, validation_message = validate_resume_content(normalized_text,first_name,last_name)
    is_valid, validation_message = validate_resume_content(normalized_text)
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

    # --- Return latest analysis result ---
    return jsonify({
        "normalized_text" : normalized_text, 
        "duplicate": False,
        "message": "New resume analyzed successfully.",
        "analysis_results": response_content,
        "score": response_json.get("score", 0),
        "quick_fixes": response_json.get("quick_fixes", []),
        "total_stored": len(existing_value),
        "file_name": resume_file.filename,
        "encrypted_file_name": encrypted_filename,  #  included in response
        "file_size": file_size,  # Added field
        "resume_hash": resume_hash

    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)





