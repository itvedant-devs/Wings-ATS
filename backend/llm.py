import os, re
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = None
if GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
        print("Groq client initialized.")
    except Exception as e:
        print(f"Error initializing Groq client: {e}")
else:
    print("Warning: GROQ_API_KEY not set. Groq API calls will fail.")

def get_groq_response(resume_text, job_description_text, prompt_template, structured_findings=None, target_job_role=""):
    if not client:
        return "Error: Groq client not initialized."

    user_content = f"Resume Content:\n{resume_text}\n"
    if job_description_text:
        user_content += f"\nJob Description:\n{job_description_text}\n"
    if target_job_role:
        user_content += f"\nTarget Job Role: {target_job_role}\n"
    if structured_findings:
        user_content += f"\nStructured Findings:\n{structured_findings}\n"

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": prompt_template},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            max_tokens=8192,
            top_p=0.9
        )
        model_output = completion.choices[0].message.content
        cleaned_output = re.sub(r'<think>.*?</think>', '', model_output, flags=re.DOTALL)
        return cleaned_output.strip()
    except Exception as e:
        return f"Error communicating with Groq API: {e}"
