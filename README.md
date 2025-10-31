#  Resume ATS Score Backend

## Project Description
This project allows users to upload their resumes, which are then analyzed and scored using AI.  
Based on the analysis, the system provides a detailed **ATS (Applicant Tracking System) score** and **recommendations** to help users improve their resumes for better job matching.

---

##  Tech Stack
- **Python**
- **Flask**
- **MySQL**
- **dotenv** (for environment variables)
- **requests / groq / other AI API packages**

---

## Setup Instructions

-Create and Activate Virtual Environment
python -m venv env
# Activate the environment
# On Windows:
env\Scripts\activate
# On macOS/Linux:
source env/bin/activate

-Install Dependencies
pip install -r requirements.txt

-Environment Variables Setup
Create a .env file in your project root directory and add your API credentials:
# .env
GROQ_API_KEY = 'Enter your API key'

-Run the Application
python app.py

