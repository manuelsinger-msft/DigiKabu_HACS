"""Constants for DigiKabu."""

from datetime import timedelta

DOMAIN = "digikabu"
BASE_URL = "https://www.digikabu.de"
CONF_API_KEY = "api_key"
UPDATE_INTERVAL = timedelta(minutes=15)
REQUEST_TIMEOUT = 30
ENDPOINTS = {
    "absences": "/api/schueler/fehlzeiten",
    "timetable": "/api/stundenplan",
    "exams": "/api/termine/schulaufgaben",
    "appointments": "/api/termine",
}
