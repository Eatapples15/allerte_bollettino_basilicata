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
        # Gestione formati "0.5" o "1,2"
        clean = val_str.replace(",", ".").strip()
        # Rimuove caratteri non numerici tranne punto e meno
        clean = re.sub(r'[^\d\.\-]', '', clean)
        if not clean: return None
        return float(clean)
    except:
        return None

def scrape_sensor_type(sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"Scraping {config['label']} da {url}...")
    
    data_list = []
    
    try:
        r = requests.get(url, headers=FAKE_HEADERS, timeout=30)
        # Usa html5lib se disponibile, altrimenti html.parser
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # LOGICA DI RICERCA MIGLIORATA
        # Cerchiamo tutte le tabelle e prendiamo quella che contiene "Stazione" nella prima riga
        tables = soup.find_all("table")
        target_table = None
        
        for t in tables:
            # Prendi le prime righe per controllare l'intestazione
            rows = t.find_all("tr")
            if not rows: continue
            
            # Controlla se nell'header c'è la parola chiave
            header_text = rows[0].text.strip()
            if "Stazione" in header_text or "STAZIONE" in header_text.upper():
                target_table = t
                break
            
            # Fallback: controlla la seconda riga se la prima è vuota
            if len(rows) > 1 and "Stazione" in rows[1].text:
                target_table = t
                break

        if not target_table:
            # Fallback estremo: prendiamo la tabella con più righe
            max_rows = 0
            for t in tables:
                l = len(t.find_all("tr"))
                if l > max_rows:
                    max_rows = l
                    target_table = t
            
            if not target_table or max_rows < 2:
                print(f"⚠️ Nessuna tabella valida trovata per {sensor_key}")
                return []

        rows = target_table.find_all("tr")
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 3:
                # Struttura tipica: Nome Stazione | Data/Ora | Valore
                nome_stazione = clean_text(cols[0].text)
                
                # Ignora righe di intestazione o nomi vuoti
                if not nome_stazione or "Stazione" in nome_stazione or "Provincia" in nome_stazione:
                    continue

                link = cols[0].find("a")
                station_id = ""
                if link and 'href' in link.attrs:
                    match = re.search(r'id=(\d+)', link['href'])
                    if match: station_id = match.group(1)

                data_ora = clean_text(cols[1].text)
                valore_raw = clean_text(cols[2].text)
                valore_num = parse_value(valore_raw)

                if valore_num is not None:
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
        print(f"❌ Errore scraping {sensor_key}: {e}")

    print(f"✅ Trovati {len(data_list)} dati per {sensor_key}")
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

    # Scrittura JSON
    try:
        with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"Salvataggio completato in {JSON_FILENAME}")
    except Exception as e:
        print(f"Errore salvataggio JSON: {e}")

if __name__ == "__main__":
    main()
