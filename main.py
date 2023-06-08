from grafana_client import GrafanaApi
import json
import requests
import os
from flask import Flask, request, jsonify, make_response, session
from flask_session import Session
from dotenv import load_dotenv, find_dotenv
import base64
import hashlib
import uuid

_ = load_dotenv(find_dotenv())

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config.from_object(__name__)
Session(app)

grafana_server = os.getenv('GRAFANA_SERVER')
username = os.getenv('GRAFANA_USERNAME')
password = os.getenv('GRAFANA_PASSWORD')
api_key = os.getenv('GRAFANA_API_KEY')

grafana = GrafanaApi.from_url(
    url=f'http://{grafana_server}', credential=(username, password))

f = open('Docs/template.json')
dashboard_template = json.load(f)
f.close()


def get_dashboard_link(uid, headers):
    url = f'http://{grafana_server}/api/short-urls'
    dashboard = grafana.dashboard.get_dashboard(uid)
    payload = {
        "path": dashboard['meta']['url'][1:]
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    return response
    # Check the response status code



def get_panels(workspace):
    panels = dashboard_template['dashboard']['panels']
    for panel in panels:
        try:
            for target in (panel['targets']):
                target['rawSql'] = target['rawSql'].replace("'template-workspace-name'", f"'{workspace}'")
        except:
            continue
    return panels


@app.route('/')
def index():
    return "Healthy"


@app.route('/api/v1/generate-dashboard', methods=['POST'])
def generate():
    data = request.get_json()
    workspace = data['workspace']
    get_uid = base64.urlsafe_b64encode(hashlib.md5(os.urandom(128)).digest())[:9].decode("utf-8")
    dashboard_uuid = str(uuid.uuid4())
    panels = get_panels(workspace)

    url = f'http://{grafana_server}/api/dashboards/db'
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    payload = {
        "dashboard": {
            "id": None,
            "uid": get_uid,
            "title": f"{workspace} Dashboard {dashboard_uuid}",
            "tags": ["templated"],
            "timezone": "browser",
            "schemaVersion": 16,
            "version": 0,
            "refresh": "25s",
            "panels": panels
        },
        "message": f"Create dashboard {workspace} {dashboard_uuid}",
        "overwrite": False
    }

    response_dashboard = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)

    # Check the response status code
    if response_dashboard.status_code != 200:
        return make_response(jsonify({'error': f'{response_dashboard.text}'}), response_dashboard.status_code)

    response_link = get_dashboard_link(get_uid,headers)
    if response_link.status_code != 200:
        return make_response(jsonify({'error': f'{response_link.text}'}), response_link.status_code)

    response_link_json = json.loads(response_link.content)
    return make_response(jsonify({"url": f"{response_link_json['url'][:-8]}",
                                  "status": {"dashboard":"success", "shortenLink":"success"}
                                  }), 200)

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000, debug=True)
