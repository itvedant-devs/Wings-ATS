# import os
# import PyPDF2
# from groq import Groq
# from docx import Document # type: ignore
# import spacy # type: ignore
# import re
# import hashlib
# import json
# from flask import Flask, request, jsonify
# from flask_cors import CORS # type: ignore
# from werkzeug.datastructures import FileStorage
# from flask_sqlalchemy import SQLAlchemy
# from dotenv import load_dotenv

# # --- Flask App Setup ---
# app = Flask(__name__)
# CORS(app)

# # --- MySQL Config ---
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:root@localhost/resume_db'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# db = SQLAlchemy(app)

# # --- Resume DB Model ---
# class ResumeAnalysis(db.Model):
#     __tablename__ = "resume_analysis"
#     id = db.Column(db.Integer, primary_key=True)
#     file_hash = db.Column(db.String(64), unique=True, nullable=False)
#     structured_findings = db.Column(db.Text, nullable=False)
#     analysis_results = db.Column(db.Text, nullable=False)
#     score = db.Column(db.Integer, nullable=True)          # new column
#     quick_fixes = db.Column(db.Text, nullable=True)

# with app.app_context():
#     db.create_all()

# # --- Configuration ---
# load_dotenv()
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# client = None
# if GROQ_API_KEY:
#     try:
#         client = Groq(api_key=GROQ_API_KEY)
#         print("Groq client initialized.")
#     except Exception as e:
#         print(f"Error initializing Groq client. Check your API key: {e}")
# else:
#     print("Warning: GROQ_API_KEY not set. Groq API calls will fail.")

# # Load spaCy model
# nlp_model = None
# try:
#     nlp_model = spacy.load('en_core_web_sm')
#     print("SpaCy model loaded.")
# except OSError:
#     print("SpaCy model not found. Run: python -m spacy download en_core_web_sm")

# # --- Utilities ---
# def compute_file_hash(file_object):
#     hasher = hashlib.sha256()
#     file_object.seek(0)
#     while chunk := file_object.read(8192):
#         hasher.update(chunk)
#     file_object.seek(0)
#     return hasher.hexdigest()

# def extract_text_from_file(file_object):
#     text = ""
#     file_extension = ""
#     if isinstance(file_object, FileStorage):
#         filename = file_object.filename
#         file_extension = os.path.splitext(filename)[1].lower()
#     elif isinstance(file_object, str):
#         filename = file_object
#         file_extension = os.path.splitext(filename)[1].lower()
#     else:
#         return None
#     try:
#         if file_extension == ".pdf":
#             reader = PyPDF2.PdfReader(file_object)
#             for page in reader.pages:
#                 text += page.extract_text() or ""
#         elif file_extension == ".docx":
#             doc = Document(file_object)
#             for para in doc.paragraphs:
#                 text += para.text + "\n"
#         else:
#             print(f"Unsupported file type: {file_extension}")
#             return None
#     except Exception as e:
#         print(f"Error reading file '{filename}': {e}")
#         return None
#     return text.strip() if text else ""

# def validate_resume_content(text):
#     if not text or len(text.split()) < 50:
#         return False, "The uploaded file seems too short to be a valid resume."
#     common_headers = ["education", "experience", "skills", "summary", "projects", "certifications"]
#     found_sections = [hdr for hdr in common_headers if hdr in text.lower()]
#     if len(found_sections) < 2:
#         return False, "The uploaded file does not appear to contain typical resume sections."
#     return True, "Resume content looks valid."

# def perform_structured_analysis(resume_text, job_description_text, nlp_model, target_job_role=""):
#     if not nlp_model:
#         return {"error": "SpaCy NLP model not loaded."}
#     jd_keywords = set(word.text.lower() for word in nlp_model(job_description_text) if not word.is_stop and word.is_alpha) if job_description_text else set()
#     resume_keywords = set(word.text.lower() for word in nlp_model(resume_text) if not word.is_stop and word.is_alpha)
#     common_jd_keywords = jd_keywords.intersection(resume_keywords)
#     keyword_match_score = (len(common_jd_keywords) / len(jd_keywords) * 100) if jd_keywords else 0
#     job_role_present = target_job_role.lower() in resume_text.lower() if target_job_role else False
#     ats_format_warnings = []
#     if len(re.findall(r'[A-Za-z]\.', resume_text)) > 5:
#         ats_format_warnings.append("Excessive use of single-letter initials (e.g., 'J. Doe') might confuse some parsers.")
#     if re.search(r'\b(Objective|Summary|Skills|Experience|Education)\b', resume_text, re.IGNORECASE) is None:
#         ats_format_warnings.append("Resume may lack standard section headers, which can hurt ATS parsing.")
#     quantification_status = "Consider adding more quantifiable achievements (numbers, percentages, currency, results)."
#     if re.search(r'\d+%|\$\d+(,\d{3})*|\d+\s*(?:million|thousand|k|x|cr)|increased|reduced|achieved|boosted|generated', resume_text, re.IGNORECASE):
#         quantification_status = "Resume appears to contain quantifiable achievements. Great!"
#     missing_sections = []
#     common_sections = ["experience", "education", "skills", "projects", "certifications", "summary"]
#     resume_lower = resume_text.lower()
#     for section in common_sections:
#         if section not in resume_lower:
#             missing_sections.append(section.capitalize())
#     structured_findings = {
#         "keyword_match_score": f"{keyword_match_score:.2f}%",
#         "target_job_role_mentioned": job_role_present,
#         "ats_format_warnings": ats_format_warnings if ats_format_warnings else ["No obvious formatting warnings found."],
#         "quantification_status": quantification_status,
#         "missing_common_sections": missing_sections if missing_sections else ["All common sections seem present."],
#     }
#     return structured_findings

# def get_groq_response(resume_text, job_description_text, prompt_template, structured_findings=None, target_job_role=""):
#     if not client:
#         return "Error: Groq client not initialized."
#     user_content = f"Resume Content:\n---\n{resume_text}\n---\n\n"
#     if job_description_text:
#         user_content += f"Job Description:\n---\n{job_description_text}\n---\n\n"
#     if target_job_role:
#         user_content += f"Target Job Role: {target_job_role}\n\n"
#     if structured_findings:
#         user_content += f"Structured Analysis Findings (Pre-LLM):\n---\n{structured_findings}\n---\n\n"
#     try:
#         completion = client.chat.completions.create(
#             model="openai/gpt-oss-20b",
#             messages=[
#                 {"role": "system", "content": prompt_template},
#                 {"role": "user", "content": user_content}
#             ],
#             temperature=0.1,
#             max_tokens=8192,
#             top_p=0.9,
#         )
#         model_output = completion.choices[0].message.content
#         cleaned_output = re.sub(r'<think>.*?</think>\s*', '', model_output, flags=re.DOTALL)
#         return cleaned_output
#     except Exception as e:
#         print(f"Error communicating with Groq API: {str(e)}")
#         return f"Error communicating with Groq API: {str(e)}"

# # --- API Endpoint ---
# @app.route('/analyze_resume', methods=['POST'])
# def analyze_resume():
#     if 'resume' not in request.files:
#         return jsonify({"error": "No resume file provided"}), 400
#     resume_file = request.files['resume']
#     target_job_role = request.form.get('target_job_role', '').strip()
#     job_description = request.form.get('job_description', '').strip()
#     if not resume_file.filename:
#         return jsonify({"error": "No selected file"}), 400

#     # --- Compute hash and check DB ---
#     file_hash = compute_file_hash(resume_file)
#     existing_entry = ResumeAnalysis.query.filter_by(file_hash=file_hash).first()
#     if existing_entry:
#         return jsonify({
#             "message": "This resume has already been analyzed.",
#             "analysis_results": existing_entry.analysis_results,
#             "structured_findings": json.loads(existing_entry.structured_findings)
#         })

#     # --- Extract and validate ---
#     file_text = extract_text_from_file(resume_file)
#     if not file_text:
#         return jsonify({"error": "Failed to extract text from resume"}), 500
#     is_valid, validation_message = validate_resume_content(file_text)
#     if not is_valid:
#         return jsonify({"error": validation_message}), 400
#     if not nlp_model:
#         return jsonify({"error": "NLP model not loaded"}), 500

#     structured_findings = perform_structured_analysis(file_text, job_description, nlp_model, target_job_role)
#     analysis_prompt_path = os.path.join(os.path.dirname(__file__), "analysis_prompt.txt")
#     try:
#         with open(analysis_prompt_path, encoding="utf-8") as f:
#             prompt_template = f.read()
#     except FileNotFoundError:
#         prompt_template = "You are an expert ATS and career advisor..."

#     response_content = get_groq_response(file_text, job_description, prompt_template, structured_findings, target_job_role)


#     try:
#         response_json = json.loads(response_content)
#     except json.JSONDecodeError:
#     # fallback if model returns plain text
#         response_json = {"score": 0, "quick_fixes": [], "raw_text": response_content}

#     # --- Store results in DB ---
#     new_entry = ResumeAnalysis(
#         file_hash=file_hash,
#         structured_findings=json.dumps(structured_findings),
#         analysis_results=response_content,
#         score=response_json.get("score", 0),
#         quick_fixes=", ".join(response_json.get("quick_fixes", []))

#     )
#     db.session.add(new_entry)
#     db.session.commit()

#     return jsonify({"analysis_results": response_content, "structured_findings": structured_findings})

# if __name__ == '__main__':
#     app.run(debug=True, port=5000)











from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.datastructures import FileStorage
from flask_sqlalchemy import SQLAlchemy
import os, json, re

from config import Config
from models import db, ResumeAnalysis
from utils import (
    compute_file_hash,
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

    # --- Compute hash and check DB ---
    file_hash = compute_file_hash(resume_file)
    existing_entry = ResumeAnalysis.query.filter_by(file_hash=file_hash).first()
    if existing_entry:
        return jsonify({
            "message": "This resume has already been analyzed.",
            "analysis_results": existing_entry.analysis_results,
            "structured_findings": json.loads(existing_entry.structured_findings)
        })

    # --- Extract and validate ---
    file_text = extract_text_from_file(resume_file)
    if not file_text:
        return jsonify({"error": "Failed to extract text from resume"}), 500

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
        file_hash=file_hash,
        structured_findings=json.dumps(structured_findings),
        analysis_results=response_content,
        score=response_json.get("score", 0),
        quick_fixes=", ".join(response_json.get("quick_fixes", []))
    )
    db.session.add(new_entry)
    db.session.commit()

    return jsonify({
        "analysis_results": response_content,
        "structured_findings": structured_findings
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)


