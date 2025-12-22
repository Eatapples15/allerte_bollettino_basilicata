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
    "idrometria": {"code": "I", "label": "Idrometri", "unit": "m", "threshold": 2.0},
    "pluviometria": {"code": "P", "label": "Pluviometri", "unit": "mm", "threshold": 40.0},
    "anemometria": {"code": "VV", "label": "Anemometri", "unit": "m/s", "threshold": 15.0},
    "termometria": {"code": "T", "label": "Termometri", "unit": "°C", "threshold": 38.0},
    "nivometria": {"code": "N", "label": "Nivometri", "unit": "cm", "threshold": 5.0}
}

FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text.replace("\xa0", " ")).strip()

def parse_value(val_str):
    try:
        if not val_str: return None
        # Rimuovi unità di misura (es. "mm", "m") e spazi
        clean = re.sub(r'[^\d\.,\-]', '', val_str)
        # Sostituisci virgola con punto
        clean = clean.replace(",", ".")
        return float(clean)
    except:
        return None

def scrape_sensor_bs4(sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"\n--- Scraping {config['label']} ({url}) ---")
    
    data_list = []
    
    try:
        r = requests.get(url, headers=FAKE_HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Cerca la tabella con id "rilevazioni"
        table = soup.find("table", {"id": "rilevazioni"})
        if not table:
            print("⚠️ Tabella 'rilevazioni' non trovata.")
            return []

        # Cerca il body della tabella
        tbody = table.find("tbody")
        if not tbody:
            print("⚠️ Tbody non trovato.")
            return []

        rows = tbody.find_all("tr")
        print(f"📊 Righe trovate: {len(rows)}")

        for row in rows:
            cols = row.find_all("td")
            
            # La struttura standard ha circa 6 colonne
            if len(cols) < 5: continue
            
            # 1. Stazione e ID (Colonna 0)
            col_stazione = cols[0]
            nome_stazione = clean_text(col_stazione.text)
            
            link = col_stazione.find("a")
            station_id = ""
            if link and 'href' in link.attrs:
                match = re.search(r'id=(\d+)', link['href'])
                if match: station_id = match.group(1)

            # 2. Valore (Colonna 3 - indice 3 perché si parte da 0)
            # Spesso è dentro un <strong> e un <a>
            valore_raw = clean_text(cols[3].text)
            valore_num = parse_value(valore_raw)

            # 3. Data/Ora (Colonna 4)
            data_ora = clean_text(cols[4].text)

            # Filtri validità
            if not nome_stazione or valore_num is None: continue

            # Se l'orario è solo ore (es "12:00"), aggiungi la data di oggi
            if len(data_ora) <= 5:
                today = datetime.datetime.now().strftime("%d/%m/%Y")
                data_ora = f"{today} {data_ora}"

            status = "normal"
            if abs(valore_num) >= config['threshold']: status = "alert"
            
            data_list.append({
                "id": station_id,
                "nome": nome_stazione,
                "data": data_ora,
                "valore": valore_num,
                "status": status
            })

    except Exception as e:
        print(f"❌ Errore: {e}")

    print(f"✅ Record estratti: {len(data_list)}")
    return data_list

def main():
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    total_records = 0
    for key, config in SENSORI.items():
        readings = scrape_sensor_bs4(key, config)
        final_data["sensori"][key] = {
            "meta": config,
            "dati": readings
        }
        total_records += len(readings)

    try:
        with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Salvataggio completato ({total_records} sensori totali)")
    except Exception as e:
        print(f"❌ Errore scrittura file: {e}")

if __name__ == "__main__":
    main()
