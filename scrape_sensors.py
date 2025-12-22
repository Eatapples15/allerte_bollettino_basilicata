
import requests
from bs4 import BeautifulSoup
import json
import datetime
import os
import re

# CONFIGURAZIONE URL
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"
JSON_FILENAME = "dati_sensori.json"

# MAPPATURA TIPI SENSORI
SENSORI = {
    "idrometria": {"code": "ID", "label": "Idrometri", "unit": "m", "icon": "fa-water", "threshold": 2.5}, # Soglia allerta generica
    "pluviometria": {"code": "PL", "label": "Pluviometri", "unit": "mm", "icon": "fa-cloud-rain", "threshold": 40.0},
    "anemometria": {"code": "VV", "label": "Anemometri", "unit": "m/s", "icon": "fa-wind", "threshold": 20.0}, # ~72 km/h
    "termometria": {"code": "TE", "label": "Termometri", "unit": "°C", "icon": "fa-thermometer-half", "threshold": 35.0},
    "nivometria": {"code": "NI", "label": "Nivometri", "unit": "cm", "icon": "fa-snowflake", "threshold": 1.0}
}

FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def clean_text(text):
    return text.replace("\xa0", " ").strip()

def parse_value(val_str):
    try:
        # Gestisce formati come "0.5" o "1,2"
        clean = val_str.replace(",", ".").strip()
        # Rimuove unità di misura se attaccate
        clean = re.sub(r'[^\d\.\-]', '', clean)
        return float(clean)
    except:
        return None

def scrape_sensor_type(sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"Scraping {config['label']} da {url}...")
    
    data_list = []
    
    try:
        r = requests.get(url, headers=FAKE_HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Cerca la tabella dei dati
        # Solitamente è una tabella standard. Cerchiamo tr che contengono dati.
        tables = soup.find_all("table")
        
        target_table = None
        for t in tables:
            # Euristica: la tabella dati ha spesso header specifici o molte righe
            if len(t.find_all("tr")) > 5:
                target_table = t
                break
        
        if not target_table:
            print(f"Nessuna tabella trovata per {sensor_key}")
            return []

        rows = target_table.find_all("tr")
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 3:
                # Struttura tipica: Nome Stazione | Data/Ora | Valore
                # A volte c'è un link sulla stazione
                nome_stazione = clean_text(cols[0].text)
                
                # Ignora righe di intestazione o vuote
                if not nome_stazione or "Stazione" in nome_stazione:
                    continue

                # Estrazione Link ID (utile per dettagli futuri)
                link = cols[0].find("a")
                station_id = ""
                if link and 'href' in link.attrs:
                    # id=331200
                    match = re.search(r'id=(\d+)', link['href'])
                    if match:
                        station_id = match.group(1)

                data_ora = clean_text(cols[1].text)
                valore_raw = clean_text(cols[2].text)
                valore_num = parse_value(valore_raw)

                if valore_num is not None:
                    # Calcolo Stato Allerta (Semplificato)
                    status = "normal"
                    if valore_num >= config['threshold']:
                        status = "alert"
                    
                    data_list.append({
                        "id": station_id,
                        "nome": nome_stazione,
                        "data": data_ora,
                        "valore": valore_num,
                        "status": status
                    })

    except Exception as e:
        print(f"Errore scraping {sensor_key}: {e}")

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

    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
    
    print(f"Salvataggio completato in {JSON_FILENAME}")

if __name__ == "__main__":
    main()
