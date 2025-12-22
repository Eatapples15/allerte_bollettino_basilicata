import requests
from bs4 import BeautifulSoup
import json
import datetime
import re
import sys

# CONFIGURAZIONE URL
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"
JSON_FILENAME = "dati_sensori.json"

SENSORI = {
    "idrometria": {"code": "ID", "label": "Idrometri", "unit": "m", "icon": "fa-water", "threshold": 2.0},
    "pluviometria": {"code": "PL", "label": "Pluviometri", "unit": "mm", "icon": "fa-cloud-rain", "threshold": 40.0},
    "anemometria": {"code": "VV", "label": "Anemometri", "unit": "m/s", "icon": "fa-wind", "threshold": 15.0},
    "termometria": {"code": "TE", "label": "Termometri", "unit": "°C", "icon": "fa-thermometer-half", "threshold": 35.0},
    "nivometria": {"code": "NI", "label": "Nivometri", "unit": "cm", "icon": "fa-snowflake", "threshold": 5.0}
}

# Headers completi per sembrare un vero browser
FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://centrofunzionale.regione.basilicata.it/it/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

def clean_text(text):
    if not text: return ""
    # Rimuove spazi non standard e spazi multipli
    return re.sub(r'\s+', ' ', text.replace("\xa0", " ")).strip()

def parse_value(val_str):
    try:
        if not val_str: return None
        # Sostituisce virgola con punto
        clean = val_str.replace(",", ".").strip()
        # Estrae solo la parte numerica (gestisce anche negativi)
        match = re.search(r'-?\d+(\.\d+)?', clean)
        if not match: return None
        return float(match.group(0))
    except:
        return None

def scrape_sensor_type(session, sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"\n--- Analisi {config['label']} ({url}) ---")
    
    data_list = []
    
    try:
        r = session.get(url, headers=FAKE_HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # DEBUG: Stampa il titolo della pagina per capire se siamo stati bloccati
        page_title = soup.title.string.strip() if soup.title else "Nessun Titolo"
        print(f"📄 Titolo Pagina rilevato: {page_title}")
        
        # DEBUG: Stampa lunghezza contenuto
        print(f"📦 Bytes scaricati: {len(r.text)}")

        all_rows = soup.find_all("tr")
        print(f"🔎 Righe totali trovate nel HTML: {len(all_rows)}")
        
        debug_first_row = True # Per stampare solo la prima riga trovata come test

        for row in all_rows:
            # Cerca sia td che th
            cols = row.find_all(['td', 'th'])
            
            if len(cols) < 3:
                continue
                
            # Estrai testo pulito
            raw_cols = [clean_text(c.text) for c in cols]
            
            # LOGICA DI DEBUG PER CAPIRE COSA VEDE LO SCRIPT
            if debug_first_row and len(raw_cols) >= 3:
                print(f"   [DEBUG RIGHE] Prima riga grezza trovata: {raw_cols}")
                debug_first_row = False

            # Verifica colonne
            nome_stazione = raw_cols[0]
            data_ora = raw_cols[1]
            valore_raw = raw_cols[2]
            
            # FILTRI
            # 1. Scarta intestazioni o righe vuote
            if not nome_stazione or "Stazione" in nome_stazione or "Provincia" in nome_stazione:
                continue
                
            # 2. Scarta se la colonna 3 non ha numeri
            valore_num = parse_value(valore_raw)
            if valore_num is None:
                continue

            # 3. Estrazione ID dal link (opzionale)
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
        print(f"❌ Errore critico: {e}")

    print(f"✅ Record validi estratti: {len(data_list)}")
    return data_list

def main():
    # Usa una sessione per gestire i cookie (come un browser reale)
    session = requests.Session()
    
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    total_records = 0
    for key, config in SENSORI.items():
        readings = scrape_sensor_type(session, key, config)
        final_data["sensori"][key] = {
            "meta": config,
            "dati": readings
        }
        total_records += len(readings)

    # Scrittura JSON
    try:
        with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Salvataggio completato: {JSON_FILENAME}")
        print(f"📊 Totale sensori aggiornati: {total_records}")
    except Exception as e:
        print(f"❌ Errore scrittura file: {e}")

if __name__ == "__main__":
    main()
