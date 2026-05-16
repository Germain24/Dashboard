import os
import json
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENDA_DIR = os.path.join(BASE_DIR, 'agenda')

def load_agenda():
    # Placeholder for future agenda logic
    return {
        "cours": [
            {"nom": "INF1000", "heure": "09:00 - 12:00", "local": "PK-1234"},
            {"nom": "MAT2000", "heure": "13:30 - 16:30", "local": "PK-5678"}
        ],
        "travail": {
            "prochain": "Samedi 10:00 - 18:00"
        }
    }
