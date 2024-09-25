import eventlet
eventlet.monkey_patch()

import os
import pdfplumber
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import spacy
from flask_socketio import SocketIO
import uuid
from threading import Thread

# Optional: Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Ignore FutureWarnings
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Initialize Flask app
app = Flask(__name__)

# Set secret key from environment variable
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or 'default_secret_key'  # Replace 'default_secret_key' in production

# Initialize SocketIO with eventlet
socketio = SocketIO(app, async_mode='eventlet')

# Configure upload folders
UPLOAD_FOLDER_CVS = 'uploads/cvs/'
UPLOAD_FOLDER_JD = 'uploads/job_description/'
ALLOWED_EXTENSIONS = {'pdf', 'txt'}

# Ensure upload directories exist
os.makedirs(UPLOAD_FOLDER_CVS, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_JD, exist_ok=True)

app.config['UPLOAD_FOLDER_CVS'] = UPLOAD_FOLDER_CVS
app.config['UPLOAD_FOLDER_JD'] = UPLOAD_FOLDER_JD

# Load spaCy model
try:
    nlp = spacy.load('en_core_web_sm')
except OSError:
    # Handle the case where the model is not found
    from spacy.cli import download
    download('en_core_web_sm')
    nlp = spacy.load('en_core_web_sm')

# Load Sentence-BERT model
try:
    model = SentenceTransformer('all-MiniLM-L6-v2')  # You can choose a different pre-trained model
except Exception as e:
    print(f"Error loading Sentence-BERT model: {e}")
    model = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(pdf_path):
    """
    Extract text from a PDF file using pdfplumber.
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + " "
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    return text

def preprocess_text(text):
    """
    Preprocess text using spaCy: lemmatization and removal of stopwords and punctuation.
    """
    try:
        doc = nlp(text.lower())
        tokens = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct]
        return ' '.join(tokens)
    except Exception as e:
        print(f"Error during text preprocessing: {e}")
        return ""

def process_cv(file_path, index, total, sid):
    """
    Extract and preprocess text from a single CV and emit progress.
    Runs in a background thread.
    """
    raw_text = extract_text(file_path)
    if not raw_text.strip():
        return None
    processed_text = preprocess_text(raw_text)

    # Calculate progress percentage
    percent = int((index / total) * 100)

    # Emit progress update via SocketIO
    socketio.emit('progress_update', {'percent': percent}, room=sid)

    return processed_text

def process_all_cvs(jd_path, cv_paths, sid, top_n):
    """
    Background task to process all CVs.
    """
    with app.app_context():
        # Preprocess job description
        if jd_path.lower().endswith('.pdf'):
            job_description = preprocess_text(extract_text(jd_path))
        else:
            try:
                with open(jd_path, 'r', encoding='utf-8') as jd_file:
                    jd_text = jd_file.read()
                job_description = preprocess_text(jd_text)
            except Exception as e:
                print(f"Error reading job description: {e}")
                job_description = ""
                socketio.emit('processing_error', {'message': 'Error reading job description.'}, room=sid)
                return

        if not job_description:
            socketio.emit('processing_error', {'message': 'Job description is empty or invalid.'}, room=sid)
            return

        # Preprocess CVs and emit progress
        total_cvs = len(cv_paths)
        cv_texts = []
        for i, cv_path in enumerate(cv_paths, start=1):
            processed_text = process_cv(cv_path, i, total_cvs, sid)
            if processed_text:
                cv_texts.append(processed_text)
            else:
                print(f"Processed text is empty for CV: {cv_path}")

        if not cv_texts:
            socketio.emit('processing_error', {'message': 'No valid CV texts extracted. Please check your CVs.'}, room=sid)
            return

        # Compute embeddings
        try:
            all_texts = [job_description] + cv_texts
            embeddings = model.encode(all_texts)
        except Exception as e:
            print(f'Error generating embeddings: {e}')
            socketio.emit('processing_error', {'message': f'Error generating embeddings: {e}'}, room=sid)
            return

        job_embedding = embeddings[0].reshape(1, -1)
        cv_embeddings = embeddings[1:]

        # Compute similarity
        try:
            similarities = cosine_similarity(job_embedding, cv_embeddings)[0]
        except Exception as e:
            print(f'Error computing similarities: {e}')
            socketio.emit('processing_error', {'message': f'Error computing similarities: {e}'}, room=sid)
            return

        # Pair similarity with filenames
        cv_similarity = list(zip(cv_paths, similarities))

        # Sort CVs based on similarity score in descending order
        cv_similarity_sorted = sorted(cv_similarity, key=lambda x: x[1], reverse=True)

        # Select top N CVs
        top_n = min(top_n, len(cv_similarity_sorted))  # Ensure we don't select more than available
        top_cv_similarity = cv_similarity_sorted[:top_n]


        # Prepare results with similarity scores
        results = []
        for rank, (cv_path, score) in enumerate(top_cv_similarity, start=1):
            # Use the UUID-prefixed filename for download
            full_filename = os.path.basename(cv_path)
            # Remove UUID prefix for display
            filename = full_filename.split('_', 1)[1] if '_' in full_filename else full_filename
            results.append({
                'rank': rank,
                'filename': filename,
                'full_filename': full_filename,  # Pass full filename for download
                'score': f"{score:.4f}",
            })

        # Store results in a global dictionary associated with the sid
        global_results[sid] = results

        # Emit completion event
        socketio.emit('processing_complete', room=sid)

        # # Prepare results with similarity scores
        # results = []
        # for rank, (cv_path, score) in enumerate(top_cv_similarity, start=1):
        #     # Use the UUID-prefixed filename for download link
        #     full_filename = os.path.basename(cv_path)
        #     # Remove UUID prefix for display
        #     filename = full_filename.split('_', 1)[1] if '_' in full_filename else full_filename
        #     download_link = url_for('download_file', filename=full_filename, folder='cvs')
        #     results.append({
        #         'rank': rank,
        #         'filename': filename,
        #         'score': f"{score:.4f}",
        #         'download_link': download_link
        #     })

        # # Emit completion event with results
        # socketio.emit('processing_complete', room=sid)

        # # Store results in a session or temporary storage associated with the sid
        # # For simplicity, we'll store in a global dictionary (not suitable for production)
        # global_results[sid] = results

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Retrieve sid from the form data
        sid = request.form.get('sid')
        if not sid:
            return 'Session ID not found. Please try again.', 400
        
        # Retrieve top_n from the form data
        top_n = request.form.get('top_n', type=int)
        if not top_n or top_n < 1:
            return 'Invalid number of top CVs specified.', 400

        # Check if the post request has the files
        if 'cvs' not in request.files or 'job_description' not in request.files:
            return 'No file part in the request.', 400
        
        cvs = request.files.getlist('cvs')
        jd = request.files['job_description']

        # Validate and save job description
        if jd and allowed_file(jd.filename):
            jd_filename = secure_filename(jd.filename)
            jd_unique = f"{uuid.uuid4()}_{jd_filename}"
            jd_path = os.path.join(app.config['UPLOAD_FOLDER_JD'], jd_unique)
            try:
                jd.save(jd_path)
            except Exception as e:
                return f'Failed to save job description: {e}', 500
        else:
            return 'Invalid job description file. Only PDF and TXT files are allowed.', 400

        # Validate and save CVs
        saved_cv_paths = []
        for cv in cvs:
            if cv and allowed_file(cv.filename):
                cv_filename = secure_filename(cv.filename)
                cv_unique = f"{uuid.uuid4()}_{cv_filename}"
                cv_path = os.path.join(app.config['UPLOAD_FOLDER_CVS'], cv_unique)
                try:
                    cv.save(cv_path)
                    saved_cv_paths.append(cv_path)
                except Exception as e:
                    print(f'Failed to save CV {cv.filename}: {e}')
            else:
                print(f'Invalid CV file: {cv.filename}. Only PDF and TXT files are allowed.')
                continue

        if not saved_cv_paths:
            return 'No valid CVs were uploaded.', 400

        # Start background thread to process CVs
        thread = Thread(target=process_all_cvs, args=(jd_path, saved_cv_paths, sid, top_n))
        thread.start()

        return '', 202  # Return 202 Accepted to indicate processing started

    return render_template('index.html')

# Store results temporarily (not suitable for production)
global_results = {}

@app.route('/results/<sid>')
def results(sid):
    # Retrieve results associated with the sid
    results = global_results.get(sid)
    if results is None:
        return 'Results not found or not ready yet.', 404
    return render_template('results.html', results=results)

@app.route('/download/<folder>/<filename>')
def download_file(folder, filename):
    if folder == 'cvs':
        directory = app.config['UPLOAD_FOLDER_CVS']
    elif folder == 'job_description':
        directory = app.config['UPLOAD_FOLDER_JD']
    else:
        return 'Invalid folder specified.', 400
    try:
        return send_from_directory(directory, filename, as_attachment=True)
    except FileNotFoundError:
        return 'File not found.', 404

# SocketIO event handler
@socketio.on('connect')
def handle_connect():
    print('Client connected.')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected.')

if __name__ == '__main__':
    # Run the app with SocketIO and eventlet
    socketio.run(app, debug=True)
