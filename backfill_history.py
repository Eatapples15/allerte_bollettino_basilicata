import requests
import fitz  # PyMuPDF
import re
import json
import os
from datetime import datetime, timedelta

BASE_URL = "https://centrofunzionale.regione.basilicata.it"
DATA_DIR = "data"
INDEX_FILE = "data/index.json"

COLOR_MAP = {
    "VERDE": "green", "GIALLA": "yellow", "ARANCIONE": "orange", "ROSSA": "red",
    "ORDINARIA": "yellow", "MODERATA": "orange", "ELEVATA": "red", "ASSENZA DI FENOMENI": "green"
}

def get_color(text):
    t = text.upper()
    for k, v in COLOR_MAP.items():
        if k in t: return v
    return "green"

def get_max_severity(zones_dict):
    priority = {"red": 3, "orange": 2, "yellow": 1, "green": 0}
    max_sev = "green"
    for z in zones_dict:
        color = zones_dict[z].get("oggi", "green")
        if priority.get(color, 0) > priority.get(max_sev, 0):
            max_sev = color
    return max_sev

def parse_pdf(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return None
        doc = fitz.open(stream=r.content, filetype="pdf")
        text = " ".join([page.get_text() for page in doc])
        zones = ["BASI A1", "BASI A2", "BASI B", "BASI C", "BASI D", "BASI E1", "BASI E2"]
        results = {}
        oggi_text = text.split("DOMANI")[0] 
        for z in zones:
            pattern = rf"{z}[:\s]+([\w\s]+)"
            match = re.search(pattern, oggi_text, re.IGNORECASE)
            color_text = match.group(1) if match else "VERDE"
            results[z] = {"oggi": get_color(color_text)}
        return results
    except: return None

# Esecuzione
os.makedirs(DATA_DIR, exist_ok=True)
start_date = datetime(2016, 3, 3)
end_date = datetime.now()
index_data = []

current = start_date
while current <= end_date:
    d_str = current.strftime("%d_%m_%Y")
    url = f"{BASE_URL}/ew/ew_pdf/a/Bollettino_Criticita_Regione_Basilicata_{d_str}.pdf"
    zones = parse_pdf(url)
    if zones:
        max_crit = get_max_severity(zones)
        folder = current.strftime("%Y/%m")
        os.makedirs(f"{DATA_DIR}/{folder}", exist_ok=True)
        path = f"{folder}/{current.strftime('%d')}.json"
        with open(f"{DATA_DIR}/{path}", "w") as f:
            json.dump({"date": current.strftime("%d/%m/%Y"), "zones": zones}, f)
        index_data.append({"d": current.strftime("%Y-%m-%d"), "f": path, "max_criticality": max_crit})
        print(f"Archiviato: {current.strftime('%Y-%m-%d')} - {max_crit}")
    current += timedelta(days=1)

with open(INDEX_FILE, "w") as f:
    json.dump(index_data, f, indent=2)
