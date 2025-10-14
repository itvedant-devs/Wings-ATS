import os, hashlib, re
from werkzeug.datastructures import FileStorage
import PyPDF2
from docx import Document

def compute_file_hash(file_object):
    hasher = hashlib.sha256()
    file_object.seek(0)
    while chunk := file_object.read(8192):
        hasher.update(chunk)
    file_object.seek(0)
    return hasher.hexdigest()

def extract_text_from_file(file_object):
    text = ""
    file_extension = ""
    if isinstance(file_object, FileStorage):
        filename = file_object.filename
        file_extension = os.path.splitext(filename)[1].lower()
    elif isinstance(file_object, str):
        filename = file_object
        file_extension = os.path.splitext(filename)[1].lower()
    else:
        return None

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
            print(f"Unsupported file type: {file_extension}")
            return None
    except Exception as e:
        print(f"Error reading file '{filename}': {e}")
        return None
    return text.strip() if text else ""

def validate_resume_content(text):
    if not text or len(text.split()) < 50:
        return False, "The uploaded file seems too short to be a valid resume."

    common_headers = ["education", "experience", "skills", "summary", "projects", "certifications"]
    found_sections = [hdr for hdr in common_headers if hdr in text.lower()]

    if len(found_sections) < 2:
        return False, "The uploaded file does not appear to contain typical resume sections."
    return True, "Resume content looks valid."
