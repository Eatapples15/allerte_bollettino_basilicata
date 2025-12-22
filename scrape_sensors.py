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
    "Referer": "https://centrofunzionale.regione.basilicata.it/it/"
}

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text.replace("\xa0", " ")).strip()

def parse_value(val_str):
    try:
        if not val_str: return None
        # Pulisce tutto tranne numeri, punto, virgola e meno
        clean = re.sub(r'[^\d\.,\-]', '', val_str)
        clean = clean.replace(",", ".")
        # Cerca un pattern numerico valido (es. -0.5 o 12.3)
        match = re.search(r'-?\d+(\.\d+)?', clean)
        if not match: return None
        return float(match.group(0))
    except:
        return None

def scrape_sensor_vacuum(sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"\n--- Scraping {config['label']} ({url}) ---")
    
    data_list = []
    
    try:
        r = requests.get(url, headers=FAKE_HEADERS, timeout=30)
        
        # Se la pagina è troppo piccola, c'è un errore di caricamento
        if len(r.text) < 1000:
            print(f"⚠️ Pagina troppo piccola ({len(r.text)} bytes). Possibile blocco.")
            return []

        soup = BeautifulSoup(r.text, 'html.parser')

        # METODO "VACUUM": Prendi TUTTE le righe della pagina, ignorando le tabelle
        all_rows = soup.find_all("tr")
        print(f"🔎 Righe HTML totali analizzate: {len(all_rows)}")

        for row in all_rows:
            cols = row.find_all("td")
            
            # Una riga dati valida deve avere almeno 4 colonne
            # (Stazione, Comune, ID Sensore, Valore, Data)
            if len(cols) < 4: continue
            
            # --- ESTRAZIONE DATI ---
            # La struttura tipica osservata è:
            # Col 0: Stazione (con link)
            # Col 3: Valore
            # Col 4: Data
            
            col_stazione = cols[0]
            nome_stazione = clean_text(col_stazione.text)
            
            # FILTRO 1: Ignora intestazioni
            if "Stazione" in nome_stazione or "Provincia" in nome_stazione: continue
            
            # FILTRO 2: Deve esserci un valore numerico nella colonna 3
            valore_raw = clean_text(cols[3].text)
            valore_num = parse_value(valore_raw)
            if valore_num is None: continue

            # FILTRO 3: Deve esserci una data nella colonna 4
            data_ora = clean_text(cols[4].text)
            # Se la data non contiene numeri, non è valida
            if not any(char.isdigit() for char in data_ora): continue

            # Estrazione ID Stazione
            link = col_stazione.find("a")
            station_id = ""
            if link and 'href' in link.attrs:
                match = re.search(r'id=(\d+)', link['href'])
                if match: station_id = match.group(1)

            # Fix orario breve: se è solo "12:30", aggiungi la data di oggi
            if len(data_ora) <= 5 and ":" in data_ora:
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
        print(f"❌ Errore critico: {e}")

    print(f"✅ Record estratti: {len(data_list)}")
    return data_list

def main():
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    total_records = 0
    for key, config in SENSORI.items():
        readings = scrape_sensor_vacuum(key, config)
        final_data["sensori"][key] = {
            "meta": config,
            "dati": readings
        }
        total_records += len(readings)

    # Diagnostica finale
    if total_records == 0:
        print("\n⚠️ ATTENZIONE: Nessun dato estratto. Il sito potrebbe usare JavaScript.")
    
    try:
        with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Salvataggio completato ({total_records} sensori)")
    except Exception as e:
        print(f"❌ Errore scrittura file: {e}")

if __name__ == "__main__":
    main()
