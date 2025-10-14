import os, re
import spacy
from groq import Groq
from config import Config

client = None
try:
    client = Groq(api_key=Config.GROQ_API_KEY)
    print("Groq client initialized.")
except Exception as e:
    print(f"Error initializing Groq client. Check your API key: {e}")

nlp_model = None
try:
    nlp_model = spacy.load('en_core_web_sm')
    print("SpaCy model loaded.")
except OSError:
    print("SpaCy model not found. Run: python -m spacy download en_core_web_sm")

def get_groq_response(resume_text, job_description_text, prompt_template, structured_findings=None, target_job_role=""):
    if not client:
        return "Error: Groq client not initialized."

    user_content = f"Resume Content:\n---\n{resume_text}\n---\n\n"
    if job_description_text:
        user_content += f"Job Description:\n---\n{job_description_text}\n---\n\n"
    if target_job_role:
        user_content += f"Target Job Role: {target_job_role}\n\n"
    if structured_findings:
        user_content += f"Structured Analysis Findings (Pre-LLM):\n---\n{structured_findings}\n---\n\n"

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": prompt_template},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            max_tokens=8192,
            top_p=0.9,
        )
        model_output = completion.choices[0].message.content
        cleaned_output = re.sub(r'<think>.*?</think>\s*', '', model_output, flags=re.DOTALL)
        return cleaned_output
    except Exception as e:
        print(f"Error communicating with Groq API: {str(e)}")
        return f"Error communicating with Groq API: {str(e)}"
