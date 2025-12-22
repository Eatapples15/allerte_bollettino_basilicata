import requests
from bs4 import BeautifulSoup
import json
import datetime
import os
import re

# CONFIGURAZIONE URL
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"
JSON_FILENAME = "dati_sensori.json"

# MAPPATURA SENSORI
SENSORI = {
    "idrometria": {"code": "ID", "label": "Idrometri", "unit": "m", "icon": "fa-water", "threshold": 2.0},
    "pluviometria": {"code": "PL", "label": "Pluviometri", "unit": "mm", "icon": "fa-cloud-rain", "threshold": 40.0},
    "anemometria": {"code": "VV", "label": "Anemometri", "unit": "m/s", "icon": "fa-wind", "threshold": 15.0},
    "termometria": {"code": "TE", "label": "Termometri", "unit": "°C", "icon": "fa-thermometer-half", "threshold": 35.0},
    "nivometria": {"code": "NI", "label": "Nivometri", "unit": "cm", "icon": "fa-snowflake", "threshold": 5.0}
}

FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def clean_text(text):
    if not text: return ""
    return text.replace("\xa0", " ").strip()

def parse_value(val_str):
    try:
        if not val_str: return None
        clean = val_str.replace(",", ".").strip()
        # Rimuove tutto tranne numeri, punto e meno
        clean = re.sub(r'[^\d\.\-]', '', clean)
        if not clean: return None
        return float(clean)
    except:
        return None

def scrape_sensor_type(sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"--- Scraping {config['label']} ({url}) ---")
    
    data_list = []
    
    try:
        r = requests.get(url, headers=FAKE_HEADERS, timeout=30)
        # Usa html.parser standard
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # STRATEGIA "HUNTER": Cerca ovunque i dati
        # Prende TUTTE le righe di TUTTE le tabelle della pagina
        all_rows = soup.find_all("tr")
        
        for row in all_rows:
            cols = row.find_all("td")
            
            # Un dato valido deve avere almeno 3 colonne
            if len(cols) < 3:
                continue
                
            # COLONNA 1: Nome Stazione
            nome_stazione = clean_text(cols[0].text)
            
            # COLONNA 2: Data (deve contenere un ':' o '/')
            data_ora = clean_text(cols[1].text)
            
            # COLONNA 3: Valore
            valore_raw = clean_text(cols[2].text)
            
            # FILTRI DI VALIDITÀ
            # 1. Ignora intestazioni
            if "Stazione" in nome_stazione or "Provincia" in nome_stazione:
                continue
                
            # 2. La colonna 2 deve sembrare una data/ora (contiene : o /)
            if ":" not in data_ora and "/" not in data_ora:
                continue
                
            # 3. La colonna 3 deve essere un numero
            valore_num = parse_value(valore_raw)
            if valore_num is None:
                continue

            # Estrazione ID dal link (se presente)
            link = cols[0].find("a")
            station_id = ""
            if link and 'href' in link.attrs:
                match = re.search(r'id=(\d+)', link['href'])
                if match: station_id = match.group(1)

            # Calcolo stato
            status = "normal"
            if abs(valore_num) >= config['threshold']:
                status = "alert"
            
            data_list.append({
                "id": station_id,
                "nome": nome_stazione,
                "data": data_ora,
                "valore": valore_num,
                "status": status
            })

    except Exception as e:
        print(f"❌ Errore critico su {sensor_key}: {e}")

    print(f"✅ Trovati {len(data_list)} record.")
    return data_list

def main():
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    for key, config in SENSORI.items():
        readings = scrape_sensor_type(key, config)
        final_data["sensori"][key] = {
            "meta": config,
            "dati": readings
        }

    try:
        with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"Salvataggio completato: {JSON_FILENAME}")
    except Exception as e:
        print(f"Errore scrittura file: {e}")

if __name__ == "__main__":
    main()
