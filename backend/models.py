from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Meta(db.Model):
    __tablename__ = "meta"
    key = db.Column(db.Integer, primary_key=True)  # user_id
    value = db.Column(db.Text, nullable=False)    # JSON array of resumes
    type = db.Column(db.String(255), primary_key=True)
    sub_type = db.Column(db.String(255))

class User(db.Model):
    __tablename__ = 'users'  # 👈 Make sure this matches your actual MySQL table name

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    def __repr__(self):
        return f"<User {self.first_name}>"