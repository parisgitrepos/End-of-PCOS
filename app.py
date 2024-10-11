from flask import Flask, redirect, render_template, session, url_for, request, send_from_directory, flash
from os import environ as env
from urllib.parse import quote_plus, urlencode
from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from database import Patient, Provider
from bokeh.resources import INLINE

ENV_FILE = find_dotenv('.env')
if ENV_FILE:
    load_dotenv(ENV_FILE)

app = Flask(__name__, static_url_path='/assets', static_folder='assets', template_folder='')
app.secret_key = env.get("APP_SECRET_KEY")

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
    print(date)
    user_id = extract_user_id(session)
    user_name = extract_user_name(session)
    patient_key = Provider(user_id).get_patient_key(patient_id)
    survey = Patient(patient_id, patient_key, encrypted=False).get_survey_by_date(date)

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
    app.run()