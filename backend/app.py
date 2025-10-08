import os
import PyPDF2
from groq import Groq
from docx import Document # type: ignore
import spacy # type: ignore
import re
from flask import Flask, request, jsonify
from flask_cors import CORS # type: ignore
from werkzeug.datastructures import FileStorage
from dotenv import load_dotenv



# --- Flask App Setup ---
app = Flask(__name__)
CORS(app) # Enable CORS for all routes during development

# --- Configuration ---
# IMPORTANT: Never hardcode API keys in a production environment.
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = None
if GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
        print("Groq client initialized.")
        # print(f"groq api key {GROQ_API_KEY}")
    except Exception as e:
        # A more specific error for an invalid key
        print(f"Error initializing Groq client. Check your API key: {e}")
        client = None
else:
    print("Warning: GROQ_API_KEY environment variable not set. Groq API calls will fail.")
    client = None

# Load spaCy model only once
nlp_model = None
try:
    nlp_model = spacy.load('en_core_web_sm')
    print("SpaCy model 'en_core_web_sm' loaded successfully.")
except OSError:
    print("SpaCy model 'en_core_web_sm' not found. Please run: `python -m spacy download en_core_web_sm` in your terminal.")

# --- Multi-format Document Extraction ---
def extract_text_from_file(file_object):
    """
    Extracts text from PDF or DOCX file objects (Flask FileStorage or local path).
    Refactored for clarity and better error handling.
    """
    text = ""
    file_extension = ""
    
    # Handle both FileStorage objects from Flask and local file paths
    if isinstance(file_object, FileStorage):
        filename = file_object.filename
        file_extension = os.path.splitext(filename)[1].lower()
    elif isinstance(file_object, str):
        filename = file_object
        file_extension = os.path.splitext(filename)[1].lower()
    else:
        return None # Invalid file object type

    try:
        if file_extension == ".pdf":
            reader = PyPDF2.PdfReader(file_object)
            for page in reader.pages:
                text += page.extract_text() or ""
        elif file_extension == ".docx":
            doc = Document(file_object)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            print(f"Unsupported file type: {file_extension}. Please use PDF or DOCX.")
            return None
    except Exception as e:
        print(f"Error reading file '{filename}': {e}")
        return None
        
    return text.strip() if text else "" # Return a clean string or empty string

# --------------------------------------------------------------------
# 🔹 --- NEW: Resume Validation Function ---
def validate_resume_content(text):
    """
    Quick heuristic validation to check if the uploaded file looks like a resume.
    Returns (bool, message)
    """
    if not text or len(text.split()) < 50:
        return False, "The uploaded file seems too short to be a valid resume."

    common_headers = ["education", "experience", "skills", "summary", "projects", "certifications"]
    found_sections = [hdr for hdr in common_headers if hdr in text.lower()]

    if len(found_sections) < 2:
        return False, "The uploaded file does not appear to contain typical resume sections."

    return True, "Resume content looks valid."











# --- Structured NLP for Pre-processing ---
def perform_structured_analysis(resume_text, job_description_text, nlp_model, target_job_role=""):
    """
    Performs structured NLP analysis on the resume and job description.
    """
    if not nlp_model:
        return {"error": "SpaCy NLP model not loaded."}

    # Use a more robust tokenization for keyword matching
    jd_keywords = set(word.text.lower() for word in nlp_model(job_description_text) if not word.is_stop and word.is_alpha) if job_description_text else set()
    resume_keywords = set(word.text.lower() for word in nlp_model(resume_text) if not word.is_stop and word.is_alpha)
    
    common_jd_keywords = jd_keywords.intersection(resume_keywords)
    keyword_match_score = (len(common_jd_keywords) / len(jd_keywords) * 100) if jd_keywords else 0

    job_role_present = target_job_role.lower() in resume_text.lower() if target_job_role else False
    
    # Heuristic ATS format checks
    ats_format_warnings = []
    if len(re.findall(r'[A-Za-z]\.', resume_text)) > 5:
        ats_format_warnings.append("Excessive use of single-letter initials (e.g., 'J. Doe') might confuse some parsers.")
    if re.search(r'\b(Objective|Summary|Skills|Experience|Education)\b', resume_text, re.IGNORECASE) is None:
        ats_format_warnings.append("Resume may lack standard section headers, which can hurt ATS parsing.")

    quantification_status = "Consider adding more quantifiable achievements (numbers, percentages, currency, results)."
    if re.search(r'\d+%|\$\d+(,\d{3})*|\d+\s*(?:million|thousand|k|x|cr)|increased|reduced|achieved|boosted|generated', resume_text, re.IGNORECASE):
        quantification_status = "Resume appears to contain quantifiable achievements. Great!"

    missing_sections = []
    common_sections = ["experience", "education", "skills", "projects", "certifications", "summary"]
    resume_lower = resume_text.lower()
    for section in common_sections:
        if section not in resume_lower:
            missing_sections.append(section.capitalize())

    structured_findings = {
        "keyword_match_score": f"{keyword_match_score:.2f}%",
        "target_job_role_mentioned": job_role_present,
        "ats_format_warnings": ats_format_warnings if ats_format_warnings else ["No obvious formatting warnings found."],
        "quantification_status": quantification_status,
        "missing_common_sections": missing_sections if missing_sections else ["All common sections seem present."],
    }
    return structured_findings

# --- Groq response handler ---
def get_groq_response(resume_text, job_description_text, prompt_template, structured_findings=None, target_job_role=""):
    """
    Sends the resume, job description, and structured findings to the Groq LLM.
    """
    if not client:
        return "Error: Groq client not initialized. Please check your API key."

    # Concatenate all relevant information into the user message
    user_content = f"Resume Content:\n---\n{resume_text}\n---\n\n"
    if job_description_text:
        user_content += f"Job Description:\n---\n{job_description_text}\n---\n\n"
    if target_job_role:
        user_content += f"Target Job Role: {target_job_role}\n\n"
    if structured_findings:
        user_content += f"Structured Analysis Findings (Pre-LLM):\n---\n{structured_findings}\n---\n\n"
    
    # Use the correct, currently available model
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b", # Corrected model name open ai
            messages=[
                {"role": "system", "content": prompt_template},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1, # Keep low for factual, consistent analysis
            max_tokens=8192, # Max tokens for the LLM's response
            top_p=0.9, # Adjust to a more reasonable value
        )

        

        model_output= completion.choices[0].message.content
        cleaned_output = re.sub(r'<think>.*?</think>\s*', '', model_output, flags=re.DOTALL)
        return cleaned_output

    except Exception as e:
        print(f"Error communicating with Groq API: {str(e)}")
        return f"Error communicating with Groq API: {str(e)}"

# --- API Endpoints ---


@app.route('/analyze_resume', methods=['POST'])
def analyze_resume():
    if 'resume' not in request.files:
        return jsonify({"error": "No resume file provided"}), 400
    
    resume_file = request.files['resume']
    target_job_role = request.form.get('target_job_role', '').strip()
    job_description = request.form.get('job_description', '').strip()

    if not resume_file.filename:
        return jsonify({"error": "No selected file"}), 400

    file_text = extract_text_from_file(resume_file)
    if not file_text: # Check for empty string, not just None
        return jsonify({"error": "Failed to extract text from resume. Check file type or content."}), 500

    # 🔹 NEW: Validate if uploaded file is actually a resume
    is_valid, validation_message = validate_resume_content(file_text)
    if not is_valid:
        return jsonify({"error": validation_message}), 400

    if not nlp_model:
        return jsonify({"error": "NLP model not loaded. Backend setup issue."}), 500

    structured_findings = perform_structured_analysis(file_text, job_description, nlp_model, target_job_role)

    analysis_prompt_path = os.path.join(os.path.dirname(__file__), "analysis_prompt.txt")
    try:
        with open(analysis_prompt_path, encoding="utf-8") as f:
            prompt_template = f.read()
    except FileNotFoundError:
        prompt_template = """
        You are an expert ATS (Applicant Tracking System) and career advisor. Analyze the provided resume in relation to the given job description (if any) and the target job role. Provide a detailed analysis covering an ATS score (0-100) and actionable feedback.
        """
    
    response_content = get_groq_response(file_text, job_description, prompt_template, structured_findings, target_job_role)
    
    return jsonify({"analysis_results": response_content, "structured_findings": structured_findings})


if __name__ == '__main__':
    # Ensure prompt file exists
    analysis_prompt_path = os.path.join(os.path.dirname(__file__), "analysis_prompt.txt")
    if not os.path.exists(analysis_prompt_path):
        print(f"Creating default '{analysis_prompt_path}' as it was not found.")
    
    # In development, you can use debug=True. Turn off for production.
    app.run(debug=True, port=5000)