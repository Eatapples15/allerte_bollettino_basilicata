import requests
import fitz  # PyMuPDF
import re
import json
import os
from datetime import datetime, timedelta

BASE_URL = "https://centrofunzionale.regione.basilicata.it"
DATA_DIR = "data"
INDEX_FILE = "data/index.json"

PRIORITY = {"red": 3, "orange": 2, "yellow": 1, "green": 0}

COLOR_KEYWORDS = {
    "ROSSA": "red", "ELEVATA": "red",
    "ARANCIONE": "orange", "MODERATA": "orange",
    "GIALLA": "yellow", "ORDINARIA": "yellow",
    "VERDE": "green", "ASSENZA": "green"
}

BASIN_TO_ZONES = {
    "OFANTO": ["BASI A1", "BASI A2"], "BASENTO": ["BASI B", "BASI E2"],
    "BRADANO": ["BASI B", "BASI E2"], "AGRI": ["BASI C", "BASI E1"],
    "SINNI": ["BASI C", "BASI E1"], "CAVONE": ["BASI E1"],
    "NOCE": ["BASI D"], "MERCURE": ["BASI D"], "TIRRENO": ["BASI D"]
}

def get_max_severity(zones_dict):
    max_sev = "green"
    for z in zones_dict:
        color = zones_dict[z].get("oggi", "green")
        if PRIORITY.get(color, 0) > PRIORITY.get(max_sev, 0):
            max_sev = color
    return max_sev

def parse_pdf(url):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200: return None
        doc = fitz.open(stream=r.content, filetype="pdf")
        
        # Estraiamo il testo mantenendo una parvenza di struttura a righe
        full_text = ""
        for page in doc:
            full_text += page.get_text("text")
        
        lines = full_text.split('\n')
        zones_out = {z: {"oggi": "green"} for z in ["BASI A1", "BASI A2", "BASI B", "BASI C", "BASI D", "BASI E1", "BASI E2"]}
        
        # Cerchiamo solo nella parte "OGGI"
        text_upper = full_text.upper()
        parts = re.split(r"DOMANI|VALIDITÀ", text_upper)
        sezione_oggi = parts[0]
        linee_oggi = sezione_oggi.split('\n')

        found_any_color = False

        # --- LOGICA TABELLARE 2017-2025 ---
        for i, line in enumerate(linee_oggi):
            clean_line = line.strip().upper()
            # Se la riga inizia con una zona (es. BASI A1)
            for z_code in zones_out.keys():
                if z_code in clean_line:
                    # Trovata la zona, cerchiamo il colore nella riga stessa o in quella immediatamente successiva
                    # (A volte il PDF scinde zona e colore su due righe)
                    context = clean_line + " " + (linee_oggi[i+1].upper() if i+1 < len(linee_oggi) else "")
                    
                    for key, color_val in COLOR_KEYWORDS.items():
                        if key in context:
                            if PRIORITY[color_val] > PRIORITY[zones_out[z_code]["oggi"]]:
                                zones_out[z_code]["oggi"] = color_val
                                found_any_color = True

        # --- LOGICA TESTUALE 2016 (Fallback) ---
        if not found_any_color:
            for key, color_val in COLOR_KEYWORDS.items():
                if key in sezione_oggi:
                    idx = sezione_oggi.find(key)
                    chunk = sezione_oggi[idx:idx+500]
                    for basin, zones in BASIN_TO_ZONES.items():
                        if basin in chunk:
                            for z in zones:
                                if PRIORITY[color_val] > PRIORITY[zones_out[z]["oggi"]]:
                                    zones_out[z]["oggi"] = color_val

        return zones_out
    except Exception as e:
        return None

# Il resto della funzione main() rimane invariato
def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    start_date = datetime(2016, 3, 3)
    end_date = datetime.now()
    index_data = []
    current = start_date
    while current <= end_date:
        d_iso = current.strftime("%Y-%m-%d")
        url = f"{BASE_URL}/ew/ew_pdf/a/Bollettino_Criticita_Regione_Basilicata_{current.strftime('%d_%m_%Y')}.pdf"
        zones = parse_pdf(url)
        if zones:
            max_c = get_max_severity(zones)
            folder = current.strftime("%Y/%m")
            os.makedirs(f"{DATA_DIR}/{folder}", exist_ok=True)
            path = f"{folder}/{current.strftime('%d')}.json"
            with open(f"{DATA_DIR}/{path}", "w", encoding='utf-8') as f:
                json.dump({"date": current.strftime("%d/%m/%Y"), "zones": zones}, f)
            index_data.append({"d": d_iso, "f": path, "max_criticality": max_c})
            print(f"Processato: {d_iso} -> {max_c}")
        current += timedelta(days=1)
    index_data.sort(key=lambda x: x["d"])
    with open(INDEX_FILE, "w", encoding='utf-8') as f:
        json.dump(index_data, f, indent=2)

if __name__ == "__main__":
    main()