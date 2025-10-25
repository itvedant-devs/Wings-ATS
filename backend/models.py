from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Meta(db.Model):
    __tablename__ = "meta"
    key = db.Column(db.Integer, primary_key=True)  # user_id
    value = db.Column(db.Text, nullable=False)    # JSON array of resumes
    type = db.Column(db.String(255), nullable=False)
    sub_type = db.Column(db.String(255))
