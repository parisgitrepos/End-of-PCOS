import os

import pymongo
import certifi
from datetime import datetime
from bokeh.plotting import figure
from bokeh.embed import components
from dotenv import find_dotenv, load_dotenv

ENV_FILE = find_dotenv('.env')
if ENV_FILE:
    load_dotenv(ENV_FILE)

db_conn = os.getenv('CONNECTION_STRING')
date_format = '%m-%d-%Y'

class Patient:

    def __init__(self, patient_id, patient_key, encrypted):
        self.client = pymongo.MongoClient(db_conn, tlsCAFile=certifi.where())
        self.patient_id = patient_id
        self.patient_details = self.client['Patients'][patient_id].find_one({'entry_type': 'patient_details'})
        self.encrypted = encrypted
        self.patient_key = patient_key

    @staticmethod
    def verify_patient_credentials(patient_id, patient_key, encrypted=False):
        if not encrypted:
            client = pymongo.MongoClient(db_conn, tlsCAFile=certifi.where())
            if patient_id in client['Patients'].list_collection_names():
                return True
            else:
                return False
        else:
            pass  # TODO

    def _get_fsh_data(self):
        if self.encrypted:
            # TODO
            pass
        else:
            return self.client['Patients'][self.patient_id].find_one({'entry_type': 'fsh_values'})['fsh_values']

    def _get_lh_data(self):
        if self.encrypted:
            # TODO
            pass
        else:
            return self.client['Patients'][self.patient_id].find_one({'entry_type': 'lh_values'})['lh_values']

    def get_range(self, metric='lh'):
        data = self._get_lh_data() if metric == 'lh' else self._get_fsh_data()
        if not data:
            return ['n/a', 'n/a']
        data = list(data.values())
        data = [float(val) for val in data]
        return [min(data), max(data)]

    def get_chart(self, metric='lh'):
        if metric == 'lh':
            data = self._get_lh_data()
        elif metric == 'fsh':
            data = self._get_fsh_data()

        # TODO Handle no lh/fsh data

        dates = [datetime.strptime(date, date_format) for date in data.keys()]
        vals = list(data.values())
        vals = [float(val) for val in vals]

        chart = figure(height=350, x_axis_type='datetime', sizing_mode='stretch_width')
        chart.xaxis.axis_label = 'Date'
        chart.yaxis.axis_label = 'IU/L' if metric == 'lh' else 'mIU/ml'
        chart.line(dates, vals, line_color='pink')
        chart.varea(x=dates, y1=0, y2=vals, alpha=0.1, fill_color='LightPink')

        for date, val in zip(dates, vals):
            chart.scatter(date, val, color='HotPink', size=5)

        chart.toolbar_location = None

        return components(chart)

    def get_first_name(self):
        if self.encrypted:
            return self._decrypt_string(self.patient_details['first_name'])
        else:
            return self.patient_details['first_name']

    def get_last_name(self):
        if self.encrypted:
            return self._decrypt_string(self.patient_details['last_name'])
        else:
            return self.patient_details['last_name']

    def get_recent_test_strip_photo(self):
        if self.encrypted:
            pass
        else:
            photo_mime = 'mime/jpg'
            photo = self.client['Patients'][self.patient_id].find_one({'entry_type': 'test_strip_photo'})['photo']
            photo = f'data:{photo_mime};base64,{photo}'
            return photo

    def _get_all_questions(self) -> dict:
        if not self.encrypted:
            question_entries = self.client['Patients'][self.patient_id].find({'entry_type': 'questions'})
            questions = dict()
            for entry in question_entries:
                date = entry['date']
                questions[datetime.strptime(date, date_format)] = entry['questions']

            questions = dict(sorted(questions.items(), reverse=True))

            return questions

    def get_formatted_questions(self, date=None):
        questions = self._get_all_questions()
        html_formatted = ""

        for item in questions.items():
            date = item[0].strftime(date_format)
            questions = item[1]
            formatted_string = f'<b>{date}</b><br>'
            for question, answer in zip(questions.keys(), questions.values()):
                formatted_string += f"{question}: <i>{answer}</i><br>"
            html_formatted += formatted_string + "<br><br>"

        return html_formatted

    def get_survey_by_date(self, date):
        questions = self._get_all_questions()
        date = datetime.strptime(date, date_format)
        questions = questions[date]
        return questions

    def get_surveys_overview(self):
        surveys = self._get_all_questions()
        surveys_overview = list()
        for survey_key, survey_val in zip(surveys.keys(), surveys.values()):
            survey_dict = dict()

            survey_dict['date'] = survey_key.strftime(date_format)

            survey_dict['period'] = survey_val['On period?']
            if survey_dict['period'] == 'Yes':
                survey_dict['flow_rate'] = survey_val['Flow rate?']
            else:
                survey_dict['flow_rate'] = 'n/a'

            survey_dict['hair_changes'] = survey_val['Changes in hair?']

            survey_dict['pain_level'] = survey_val['Pain level?']

            surveys_overview.append(survey_dict)

        return surveys_overview

    def get_last_period(self):
        surveys = self._get_all_questions()
        period_dates = list()

        for survey_key, survey_val in zip(surveys.keys(), surveys.values()):
            if survey_val['On period?'] == 'Yes':
                period_dates.append(survey_key)

        return max(period_dates).strftime(date_format)




    def _decrypt_string(self, data):
        pass # TODO
        return False

    def _decrypt_dict(self, data):
        pass # TODO
        return False


class Provider:

    def __init__(self, user_id):
        self.user_id = user_id
        self.client = pymongo.MongoClient(db_conn, tlsCAFile=certifi.where())['Providers']

        collections_list = self.client.list_collection_names()
        patient_list_exists = self.client[self.user_id].find_one({'document_type': 'patient_list'}) is not None
        if self.user_id not in collections_list:
            self.client.create_collection(self.user_id)
            self.client[self.user_id].insert_one({
                'document_type': 'patient_list',
                'patient_list': {}
            })

        if not patient_list_exists:
            self.client[self.user_id].insert_one({'document_type': 'patient_list', 'patient_list': {}})

    def get_patient_list(self):
        doc_filter = {'document_type': 'patient_list'}
        doc = self.client[self.user_id].find_one(doc_filter)['patient_list']

        return doc

    def add_patient(self, patient_id, patient_key):
        patient_list = self.get_patient_list()

        patient_list[patient_id] = patient_key

        self.client[self.user_id].replace_one({'document_type': 'patient_list'}, {
            'document_type': 'patient_list',
            'patient_list': patient_list
        })

    def drop_patient(self, patient_id):
        patient_list = self.get_patient_list()
        patient_list.pop(patient_id)

        self.client[self.user_id].replace_one({'document_type': 'patient_list'}, {
            'document_type': 'patient_list',
            'patient_list': patient_list
        })

    def patients_overview(self, encrypted=False):
        patient_ids = list(self.get_patient_list().keys())
        patient_keys = list(self.get_patient_list().values())
        patients_overview = list()

        if len(patient_ids) > 0:
            for patient_id, patient_key in zip(patient_ids, patient_keys):
                patient = Patient(patient_id=patient_id, patient_key=None, encrypted=encrypted)
                patients_overview.append({
                    'patient_id': patient_id,
                    'first_name': patient.get_first_name(),
                    'last_name': patient.get_last_name()
                  })
        else:
            patients_overview = list()

        return patients_overview

    def get_patient_key(self, patient_id):
        return self.get_patient_list()[patient_id]