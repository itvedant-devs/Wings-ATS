import re

def perform_structured_analysis(resume_text, job_description_text, nlp_model, target_job_role=""):
    if not nlp_model:
        return {"error": "SpaCy NLP model not loaded."}

    jd_keywords = set(word.text.lower() for word in nlp_model(job_description_text) if not word.is_stop and word.is_alpha) if job_description_text else set()
    resume_keywords = set(word.text.lower() for word in nlp_model(resume_text) if not word.is_stop and word.is_alpha)
    common_jd_keywords = jd_keywords.intersection(resume_keywords)
    keyword_match_score = (len(common_jd_keywords) / len(jd_keywords) * 100) if jd_keywords else 0

    job_role_present = target_job_role.lower() in resume_text.lower() if target_job_role else False

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
