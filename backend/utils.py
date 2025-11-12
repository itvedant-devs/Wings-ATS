import os, hashlib, re
from werkzeug.datastructures import FileStorage
import PyPDF2
from docx import Document

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


def contains_emoji(text):
    """Checks if text contains any emoji."""
    emoji_pattern = re.compile(
        "["                       
        "\U0001F600-\U0001F64F"   # emoticons
        "\U0001F300-\U0001F5FF"   # symbols & pictographs
        "\U0001F680-\U0001F6FF"   # transport & map symbols
        "\U0001F1E0-\U0001F1FF"   # flags
        "\U0001F900-\U0001F9FF"   # supplemental symbols
        "\U0001FA70-\U0001FAFF"   # extended pictographs
        "\U00002600-\U000026FF"   # misc symbols
        "]+", flags=re.UNICODE
    )
    return bool(emoji_pattern.search(text))



def validate_resume_content(text):
    if not text or len(text.split()) < 50:
        return False, "The uploaded file seems too short to be a valid resume."

    common_headers = ["education", "experience", "skills", "summary", "projects", "certifications"]
    found_sections = [hdr for hdr in common_headers if hdr in text.lower()]

    if len(found_sections) < 2:
        return False, "The uploaded file does not appear to contain typical resume sections."
    
    if contains_emoji(text):
        return False, "The uploaded resume contains emojis. Please upload a text-only resume."

    return True, "Resume content looks valid."


