from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class ResumeAnalysis(db.Model):
    __tablename__ = "resume_analysis"
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)   # ✅ New column added
    resume_text = db.Column(db.Text, nullable=True)
    structured_findings = db.Column(db.Text, nullable=False)
    analysis_results = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer, nullable=True)
    quick_fixes = db.Column(db.Text, nullable=True)
