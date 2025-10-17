from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.datastructures import FileStorage
from flask_sqlalchemy import SQLAlchemy
import os, json, re

from config import Config
from models import db, ResumeAnalysis
from utils import (
    extract_text_from_file,
    validate_resume_content,
)
from analysis import perform_structured_analysis
from groq_client import client, get_groq_response, nlp_model

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
    if 'resume' not in request.files:
        return jsonify({"error": "No resume file provided"}), 400

    resume_file = request.files['resume']
    target_job_role = request.form.get('target_job_role', '').strip()
    job_description = request.form.get('job_description', '').strip()

    if not resume_file.filename:
        return jsonify({"error": "No selected file"}), 400


    # --- Extract and validate ---
    file_text = extract_text_from_file(resume_file)
    if not file_text:
        return jsonify({"error": "Failed to extract text from resume"}), 500
    
    normalized_text = re.sub(r"\s+", " ", file_text.strip().lower())
    # --- Check DB for duplicate text ---
    existing_entry = ResumeAnalysis.query.filter(ResumeAnalysis.resume_text == normalized_text).first()

    if existing_entry:
        return jsonify({
        "message": "This resume has already been analyzed (same content).",
        "normalized_text": normalized_text,
        "analysis_results": existing_entry.analysis_results,
        "structured_findings": json.loads(existing_entry.structured_findings)
    })

    is_valid, validation_message = validate_resume_content(file_text)
    if not is_valid:
        return jsonify({"error": validation_message}), 400

    if not nlp_model:
        return jsonify({"error": "NLP model not loaded"}), 500

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

    # --- Store results in DB ---
    new_entry = ResumeAnalysis(
        file_name=resume_file.filename,   # ✅ Added here
        resume_text=normalized_text,
        structured_findings=json.dumps(structured_findings),
        analysis_results=response_content,
        score=response_json.get("score", 0),
        quick_fixes=", ".join(response_json.get("quick_fixes", []))
    )
    db.session.add(new_entry)
    db.session.commit()


    print(type(normalized_text))
    return jsonify({
        "normalized_text": normalized_text,
        "analysis_results": response_content,
        "structured_findings": structured_findings
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)


