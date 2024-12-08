from flask import Flask, request, jsonify, redirect, render_template, session, url_for, send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from os import environ as env
from datetime import datetime
import uuid
import re
from database import Patient, Provider
from bokeh.resources import INLINE
from urllib.parse import quote_plus, urlencode

# Load environment variables
ENV_FILE = find_dotenv('.env')
if ENV_FILE:
    load_dotenv(ENV_FILE)

# Initialize Flask app
app = Flask(__name__, static_url_path='/assets', static_folder='assets', template_folder='')

# Secret key and app configurations
app.secret_key = env.get("APP_SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///endo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy and other extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app)

# OAuth configuration
oauth = OAuth(app)
oauth.register("auth0", client_id=env.get("AUTH0_CLIENT_ID"), client_secret=env.get("AUTH0_CLIENT_SECRET"),
               client_kwargs={"scope": "openid profile email"},
               server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration')

# Models
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __init__(self, email, password):
        self.id = str(uuid.uuid4())
        self.email = email
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')


class Survey(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    is_on_period = db.Column(db.Boolean, nullable=False)
    period_flow = db.Column(db.Integer, nullable=False)
    change_frequency = db.Column(db.Integer, nullable=False)
    has_spotting = db.Column(db.Boolean, nullable=False)
    has_pain = db.Column(db.Boolean, nullable=False)
    pain_level = db.Column(db.Integer, nullable=False)
    sleep_quality = db.Column(db.Integer, nullable=False)
    pain_qualities = db.Column(db.String, nullable=False)
    pain_timing = db.Column(db.String, nullable=False)
    pain_spread = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# Helper functions
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    return len(password) >= 8

# API Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'error': 'Email and password are required'}), 400

    email = data['email'].lower()
    password = data['password']

    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400

    if not validate_password(password):
        return jsonify({'error': 'Password must be at least 8 characters long'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    try:
        # Create a new user, which will automatically hash the password in the constructor
        new_user = User(email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'Registration successful', 'patient_id': new_user.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Registration failed', 'details': str(e)}), 500


@app.route('/api/login', methods=['POST'])
def mobile_login():
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({'error': 'Email and password are required'}), 400

    email = data['email'].lower()
    password = data['password']
    user = User.query.filter_by(email=email).first()

    if user and bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Login successful', 'patient_id': user.id}), 200
    else:
        return jsonify({'error': 'Invalid email or password'}), 401

@app.route('/api/survey', methods=['POST'])
def submit_survey():
    data = request.get_json()
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    new_survey = Survey(
        id=str(uuid.uuid4()),
        user_id=user_id,
        is_on_period=data.get('isOnPeriod', False),
        period_flow=data.get('periodFlow', 0),
        change_frequency=data.get('changeFrequency', 0),
        has_spotting=data.get('hasSpotting', False),
        has_pain=data.get('hasPain', False),
        pain_level=data.get('painLevel', 0),
        sleep_quality=data.get('sleepQuality', 0),
        pain_qualities=','.join(data.get('painQualities', [])),
        pain_timing=data.get('painTiming', ''),
        pain_spread=data.get('painSpread', '')
    )

    try:
        db.session.add(new_survey)
        db.session.commit()
        return jsonify({'message': 'Survey submitted successfully', 'survey_id': new_survey.id}), 201
    except:
        db.session.rollback()
        return jsonify({'error': 'Failed to submit survey'}), 500

oauth = OAuth(app)
oauth.register("auth0", client_id=env.get("AUTH0_CLIENT_ID"), client_secret=env.get("AUTH0_CLIENT_SECRET"),
               client_kwargs={"scope": "openid profile email"},
               server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration')


def extract_user_id(s):
    return s['user']['userinfo']['sub'][6:]


def extract_user_name(s):
    user_name = s['user']['userinfo']['nickname']
    return user_name


@app.route('/')
def index():
    return redirect('/login')


@app.route('/patients')
def patients():
    if session.get('user'):  # Indicates logged in
        user_name = extract_user_name(session)
        user_id = extract_user_id(session)
        provider = Provider(user_id=user_id)
        records = provider.patients_overview(encrypted=False)
        return render_template('patients.html', user_name=user_name, records=records)
    else:
        return redirect('/login')


@app.route('/patients/<path:patient_id>')
def patient_dashboard(patient_id):
    if session.get('user'):
        user_id = extract_user_id(session)
        user_name = extract_user_name(session)
        patient_key = Provider(user_id).get_patient_key(patient_id)
        patient = Patient(patient_id, patient_key, encrypted=False)
        patient_name = patient.get_first_name() + " " + patient.get_last_name()
        fsh_script, fsh_div = patient.get_chart('fsh')
        lh_script, lh_div = patient.get_chart('lh')
        #test_strip_photo = patient.get_recent_test_strip_photo()
        surveys = patient.get_surveys_overview()
        lh_range = patient.get_range('lh')
        fsh_range = patient.get_range('fsh')
        last_period = patient.get_last_period()

        return render_template('patient_dashboard.html', fsh_script=fsh_script, fsh_div=fsh_div,
                               js_resources=INLINE.render_js(),
                               css_resources=INLINE.render_css(), user_name=user_name, patient_name=patient_name,
                               surveys=surveys, lh_div=lh_div, lh_script=lh_script, patient_id=patient_id,
                               lh_range=lh_range, fsh_range=fsh_range, last_period=last_period)
    else:
        return redirect('/login')


@app.route('/patients/<path:patient_id>/<path:date>')
def patient_survey(patient_id, date):
    try:
        print(date)
        user_id = extract_user_id(session)
        user_name = extract_user_name(session)
        patient_key = Provider(user_id).get_patient_key(patient_id)
        survey = Patient(patient_id, patient_key, encrypted=False).get_survey_by_date(date)
    except Exception as error:
        return str(error)

    return render_template('patient_survey.html', date=date, questions=survey, user_name=user_name)


@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(redirect_uri=url_for("callback", _external=True))


@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token

    return redirect("/patients")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for('index', _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )


@app.route("/add_patient", methods=['GET', 'POST'])
def add_patient():
    if session.get('user'):
        user_name = extract_user_name(session)
        if request.method == 'GET':
            return render_template('add_patient.html', user_name=user_name)

        elif request.method == 'POST':
            user_id = extract_user_id(session)
            patient_id = request.form.get('patient_id')
            patient_key = request.form.get('patient_key')

            if Patient.verify_patient_credentials(patient_id, patient_key, encrypted=False):
                provider = Provider(user_id)
                provider.add_patient(patient_id, patient_key)

                return render_template('add_patient.html', user_name=user_name)
            else:
                if session.get('_flashes'):
                    session['_flashes'].clear()
                flash('Invalid patient credentials!')
                return redirect('/add_patient')

    else:
        return redirect('/login')


@app.route('/drop_patient')
def drop_patient():
    if session.get('user'):
        user_name = extract_user_name(session)
        user_id = extract_user_id(session)
        provider = Provider(user_id=user_id)

        if not request.args.get('patient_id'):
            records = provider.patients_overview(encrypted=False)
            return render_template('drop_patient.html', user_name=user_name, user_id=user_id,
                                   records=records)
        else:
            patient_id = request.args['patient_id']
            provider.drop_patient(patient_id)
            return redirect('/patients')

    else:
        return redirect('/login')


@app.errorhandler(404)
def no_page_found(e):
    return render_template('404.html'), 404


if '__main__' == __name__:
    with app.app_context():
        db.create_all()
    app.run()