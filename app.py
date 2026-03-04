import os
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import text
from models import db, User, Questionnaire, Reference, Answer
from utils import SUPPORTED_EXTENSIONS, parse_questionnaire, parse_reference, generate_answers, export_document
from datetime import datetime

# load .env file so OPENAI_API_KEY can be set there
load_dotenv()

app = Flask(__name__)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
elif os.environ.get("VERCEL"):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/data.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
if os.environ.get("VERCEL"):
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
else:
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# initialize extensions early so queries work on first request
login_manager = LoginManager(app)
login_manager.login_view = 'login'

db.init_app(app)
with app.app_context():
    # Create initial tables if DB is new.
    db.create_all()
    # Lightweight migration for older answer tables.
    try:
        with db.engine.begin() as conn:
            answer_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(answer)"))}
            if 'snippet' not in answer_cols:
                conn.execute(text("ALTER TABLE answer ADD COLUMN snippet TEXT"))
            if 'confidence' not in answer_cols:
                conn.execute(text("ALTER TABLE answer ADD COLUMN confidence FLOAT"))
            if 'question_order' not in answer_cols:
                conn.execute(text("ALTER TABLE answer ADD COLUMN question_order INTEGER"))
            questionnaire_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(questionnaire)"))}
            if 'structure_json' not in questionnaire_cols:
                conn.execute(text("ALTER TABLE questionnaire ADD COLUMN structure_json TEXT"))
            if 'source_blob' not in questionnaire_cols:
                conn.execute(text("ALTER TABLE questionnaire ADD COLUMN source_blob BLOB"))
    except Exception as e:
        app.logger.warning(f"Schema check/migration skipped: {e}")


def allowed_upload(filename):
    return os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if not username or not password:
            flash('Username and password are required', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash('Account created', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if not username or not password:
            flash('Username and password are required', 'danger')
            return render_template('login.html')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    questionnaires = Questionnaire.query.filter_by(user_id=current_user.id).all()
    references = Reference.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', questionnaires=questionnaires, references=references)

@app.route('/delete_questionnaire/<int:qid>')
@login_required
def delete_questionnaire(qid):
    q = Questionnaire.query.get_or_404(qid)
    if q.user_id == current_user.id:
        Answer.query.filter_by(questionnaire_id=qid).delete()
        db.session.delete(q)
        db.session.commit()
        flash('Questionnaire deleted','success')
    return redirect(url_for('dashboard'))

@app.route('/delete_reference/<int:rid>')
@login_required
def delete_reference(rid):
    r = Reference.query.get_or_404(rid)
    if r.user_id == current_user.id:
        db.session.delete(r)
        db.session.commit()
        flash('Reference deleted','success')
    return redirect(url_for('dashboard'))

@app.route('/upload_questionnaire', methods=['GET', 'POST'])
@login_required
def upload_questionnaire():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            if not allowed_upload(file.filename):
                flash('Unsupported format. Use .txt, .pdf, or .xlsx', 'danger')
                return redirect(url_for('upload_questionnaire'))
            base = secure_filename(file.filename)
            filename = f"q_{current_user.id}_{datetime.utcnow().timestamp()}_{base}"
            raw_bytes = file.read()
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(path, "wb") as out:
                out.write(raw_bytes)
            try:
                text, structure = parse_questionnaire(path)
            except Exception as exc:
                flash(f'Failed to parse questionnaire: {exc}', 'danger')
                return redirect(url_for('upload_questionnaire'))
            if not text.strip():
                flash('Uploaded file could not be parsed as text', 'danger')
                return redirect(url_for('upload_questionnaire'))
            q = Questionnaire(
                user_id=current_user.id,
                filename=filename,
                content=text,
                structure_json=json.dumps(structure),
                source_blob=raw_bytes,
            )
            db.session.add(q)
            db.session.commit()
            flash('Questionnaire uploaded', 'success')
            return redirect(url_for('dashboard'))
        flash('Please choose a file to upload', 'danger')
    return render_template('upload.html', type='Questionnaire')

@app.route('/upload_reference', methods=['GET', 'POST'])
@login_required
def upload_reference():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            if not allowed_upload(file.filename):
                flash('Unsupported format. Use .txt, .pdf, or .xlsx', 'danger')
                return redirect(url_for('upload_reference'))
            base = secure_filename(file.filename)
            filename = f"r_{current_user.id}_{datetime.utcnow().timestamp()}_{base}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(path)
            try:
                text = parse_reference(path)
            except Exception as exc:
                flash(f'Failed to parse reference document: {exc}', 'danger')
                return redirect(url_for('upload_reference'))
            if not text.strip():
                flash('Uploaded file could not be parsed as text', 'danger')
                return redirect(url_for('upload_reference'))
            r = Reference(user_id=current_user.id, filename=filename, content=text)
            db.session.add(r)
            db.session.commit()
            flash('Reference document uploaded', 'success')
            return redirect(url_for('dashboard'))
        flash('Please choose a file to upload', 'danger')
    return render_template('upload.html', type='Reference')

@app.route('/generate/<int:qid>')
@login_required
def generate(qid):
    questionnaire = Questionnaire.query.get_or_404(qid)
    if questionnaire.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    refs = Reference.query.filter_by(user_id=current_user.id).all()
    answers = generate_answers(questionnaire.content, refs)
    # store answers
    Answer.query.filter_by(questionnaire_id=qid).delete()
    for idx, (q_text, a_text, cites, snippet, conf) in enumerate(answers):
        ans = Answer(
            questionnaire_id=qid,
            question_order=idx,
            question=q_text,
            answer=a_text,
            citations=cites,
            snippet=snippet,
            confidence=conf,
        )
        db.session.add(ans)
    db.session.commit()
    flash('Answers generated', 'success')
    return redirect(url_for('review', qid=qid))

@app.route('/review/<int:qid>', methods=['GET','POST'])
@login_required
def review(qid):
    questionnaire = Questionnaire.query.get_or_404(qid)
    if questionnaire.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    answers = Answer.query.filter_by(questionnaire_id=qid).order_by(Answer.question_order.asc(), Answer.id.asc()).all()
    # coverage summary calculations
    total = len(answers)
    with_cite = sum(1 for a in answers if a.citations and a.citations.strip())
    not_found = sum(1 for a in answers if a.answer and 'Not found in references' in a.answer)

    if request.method == 'POST':
        for ans in answers:
            new_ans = request.form.get(f'answer_{ans.id}')
            ans.answer = new_ans
        db.session.commit()
        return redirect(url_for('export', qid=qid))
    return render_template('review.html', questionnaire=questionnaire, answers=answers,
                           total=total, with_cite=with_cite, not_found=not_found)

@app.route('/regenerate/<int:ans_id>')
@login_required
def regenerate(ans_id):
    ans = Answer.query.get_or_404(ans_id)
    # regenerate answer for this single question using stored reference
    questionnaire = ans.questionnaire
    if questionnaire.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    refs = Reference.query.filter_by(user_id=current_user.id).all()
    new_ans = generate_answers(ans.question, refs)[0]
    # new_ans is tuple (q, text, cite, snippet, conf)
    ans.answer = new_ans[1]
    ans.citations = new_ans[2]
    ans.snippet = new_ans[3]
    ans.confidence = new_ans[4]
    db.session.commit()
    flash('Answer regenerated', 'success')
    return redirect(url_for('review', qid=ans.questionnaire_id))

@app.route('/export/<int:qid>')
@login_required
def export(qid):
    questionnaire = Questionnaire.query.get_or_404(qid)
    if questionnaire.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('dashboard'))
    answers = Answer.query.filter_by(questionnaire_id=qid).order_by(Answer.question_order.asc(), Answer.id.asc()).all()
    outpath = export_document(questionnaire, answers, app.config['UPLOAD_FOLDER'])
    return send_file(outpath, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
