import requests
import fitz  # PyMuPDF
import re
import json
import os
from datetime import datetime, timedelta

BASE_URL = "https://centrofunzionale.regione.basilicata.it"
DATA_DIR = "data"
INDEX_FILE = "data/index.json"

# Mappatura potenziata dei termini usati nei PDF negli anni
COLOR_MAP = {
    "ROSSA": "red", "ELEVATA": "red",
    "ARANCIONE": "orange", "MODERATA": "orange",
    "GIALLA": "yellow", "ORDINARIA": "yellow",
    "VERDE": "green", "ASSENZA DI FENOMENI": "green", "NON SIGNIFICATIVA": "green"
}

def get_color(text):
    t = text.upper()
    # Ordine di controllo: dal più grave al meno grave
    if any(x in t for x in ["ROSSA", "ELEVATA"]): return "red"
    if any(x in t for x in ["ARANCIONE", "MODERATA"]): return "orange"
    if any(x in t for x in ["GIALLA", "ORDINARIA"]): return "yellow"
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
        r = requests.get(url, timeout=15)
        if r.status_code != 200: return None
        
        doc = fitz.open(stream=r.content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        
        # Pulizia testo per facilitare la regex
        text = " ".join(text.split())
        
        zones = ["BASI A1", "BASI A2", "BASI B", "BASI C", "BASI D", "BASI E1", "BASI E2"]
        results = {}
        
        # Isolo la parte relativa a OGGI (di solito prima della parola DOMANI)
        parts = re.split(r"DOMANI|validità", text, flags=re.IGNORECASE)
        oggi_text = parts[0]
        
        for z in zones:
            # Cerco la zona e prendo le 30 lettere successive per trovare il colore
            pattern = rf"{z}\s*(?:[:\-\s]+)?\s*([A-Z\s]{{1,30}})"
            match = re.search(pattern, oggi_text, re.IGNORECASE)
            
            if match:
                color_found = get_color(match.group(1))
                results[z] = {"oggi": color_found}
            else:
                results[z] = {"oggi": "green"}
                
        return results
    except Exception as e:
        print(f"Errore parsing {url}: {e}")
        return None

# Esecuzione
os.makedirs(DATA_DIR, exist_ok=True)
start_date = datetime(2016, 3, 3)
end_date = datetime.now()
index_data = []

# Carica indice esistente se vuoi evitare di rifare tutto da zero
if os.path.exists(INDEX_FILE):
    with open(INDEX_FILE, "r") as f:
        index_data = json.load(f)
    processed_dates = {e['d'] for e in index_data}
else:
    processed_dates = set()

current = start_date
while current <= end_date:
    d_iso = current.strftime("%Y-%m-%d")
    
    if d_iso in processed_dates:
        current += timedelta(days=1)
        continue

    d_str = current.strftime("%d_%m_%Y")
    url = f"{BASE_URL}/ew/ew_pdf/a/Bollettino_Criticita_Regione_Basilicata_{d_str}.pdf"
    
    zones = parse_pdf(url)
    if zones:
        max_crit = get_max_severity(zones)
        folder = current.strftime("%Y/%m")
        os.makedirs(f"{DATA_DIR}/{folder}", exist_ok=True)
        path = f"{folder}/{current.strftime('%d')}.json"
        
        with open(f"{DATA_DIR}/{path}", "w", encoding='utf-8') as f:
            json.dump({"date": current.strftime("%d/%m/%Y"), "zones": zones}, f)
        
        index_data.append({"d": d_iso, "f": path, "max_criticality": max_crit})
        print(f"Archiviato: {d_iso} - {max_crit}")
    
    current += timedelta(days=1)

# Ordina e salva l'indice
index_data.sort(key=lambda x: x["d"])
with open(INDEX_FILE, "w", encoding='utf-8') as f:
    json.dump(index_data, f, indent=2)
