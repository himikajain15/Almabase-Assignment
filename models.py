from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    questionnaires = db.relationship('Questionnaire', backref='user', lazy=True)
    references = db.relationship('Reference', backref='user', lazy=True)

class Questionnaire(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    structure_json = db.Column(db.Text, nullable=True)
    source_blob = db.Column(db.LargeBinary, nullable=True)
    answers = db.relationship('Answer', backref='questionnaire', lazy=True)

class Reference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    questionnaire_id = db.Column(db.Integer, db.ForeignKey('questionnaire.id'), nullable=False)
    question_order = db.Column(db.Integer, nullable=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=True)
    citations = db.Column(db.Text, nullable=True)
    snippet = db.Column(db.Text, nullable=True)  # small piece of evidence
    confidence = db.Column(db.Float, nullable=True)  # 0.0-1.0 confidence score
