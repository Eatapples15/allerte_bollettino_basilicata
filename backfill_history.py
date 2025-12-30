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
    except:
        return None

# Ciclo dal 3 Marzo 2016 a oggi
start_date = datetime(2016, 3, 3)
end_date = datetime.now()
index_data = []

current = start_date
while current <= end_date:
    d_str = current.strftime("%d_%m_%Y")
    url = f"{BASE_URL}/ew/ew_pdf/a/Bollettino_Criticita_Regione_Basilicata_{d_str}.pdf"
    
    zones = parse_pdf(url)
    if zones:
        folder = current.strftime("%Y/%m")
        os.makedirs(f"{DATA_DIR}/{folder}", exist_ok=True)
        path = f"{folder}/{current.strftime('%d')}.json"
        
        with open(f"{DATA_DIR}/{path}", "w") as f:
            json.dump({"date": current.strftime("%d/%m/%Y"), "zones": zones}, f)
        
        index_data.append({"d": current.strftime("%Y-%m-%d"), "f": path})
        print(f"Archiviato: {current.strftime('%Y-%m-%d')}")
    
    current += timedelta(days=1)

with open(INDEX_FILE, "w") as f:
    json.dump(index_data, f, indent=2)
