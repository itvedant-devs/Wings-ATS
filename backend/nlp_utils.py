import spacy
import re

def load_spacy_model():
    try:
        nlp = spacy.load("en_core_web_sm")
        print("SpaCy model loaded successfully.")
        return nlp
    except OSError:
        print("SpaCy model not found. Run: python -m spacy download en_core_web_sm")
        return None

def perform_structured_analysis(resume_text, job_description_text, nlp_model, target_job_role=""):
    if not nlp_model:
        return {"error": "SpaCy model not loaded."}

    jd_keywords = {
        word.text.lower() for word in nlp_model(job_description_text)
        if not word.is_stop and word.is_alpha
    } if job_description_text else set()

    resume_keywords = {
        word.text.lower() for word in nlp_model(resume_text)
        if not word.is_stop and word.is_alpha
    }

    common_jd_keywords = jd_keywords.intersection(resume_keywords)
    keyword_match_score = (len(common_jd_keywords) / len(jd_keywords) * 100) if jd_keywords else 0

    job_role_present = target_job_role.lower() in resume_text.lower() if target_job_role else False

    ats_format_warnings = []
    if len(re.findall(r'[A-Za-z]\.', resume_text)) > 5:
        ats_format_warnings.append("Too many initials (e.g., 'J. Doe') may confuse parsers.")
    if not re.search(r'\b(Objective|Summary|Skills|Experience|Education)\b', resume_text, re.IGNORECASE):
        ats_format_warnings.append("Resume may lack standard section headers.")

    quantification_status = "Consider adding quantifiable achievements."
    if re.search(r'\d+%|\$\d+|increased|reduced|achieved|boosted|generated', resume_text, re.IGNORECASE):
        quantification_status = "Resume includes quantifiable achievements."

    common_sections = ["experience", "education", "skills", "projects", "certifications", "summary"]
    missing_sections = [s.capitalize() for s in common_sections if s not in resume_text.lower()]

    return {
        "keyword_match_score": f"{keyword_match_score:.2f}%",
        "target_job_role_mentioned": job_role_present,
        "ats_format_warnings": ats_format_warnings or ["No major formatting issues found."],
        "quantification_status": quantification_status,
        "missing_common_sections": missing_sections or ["All common sections present."]
    }
