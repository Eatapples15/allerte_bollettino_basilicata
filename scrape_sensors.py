import requests
from bs4 import BeautifulSoup
import json
import datetime
import re
import sys

# CONFIGURAZIONE URL
HOME_URL = "https://centrofunzionale.regione.basilicata.it/it/"
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"
JSON_FILENAME = "dati_sensori.json"

# NUOVI CODICI CORRETTI (Grazie alla tua segnalazione)
SENSORI = {
    "idrometria": {
        "code": "I",  # Era ID
        "label": "Idrometri", 
        "unit": "m", 
        "threshold": 2.0 
    },
    "pluviometria": {
        "code": "P",  # Era PL
        "label": "Pluviometri", 
        "unit": "mm", 
        "threshold": 40.0 
    },
    "anemometria": {
        "code": "VV", # Corretto
        "label": "Anemometri", 
        "unit": "m/s", 
        "threshold": 15.0 
    },
    "termometria": {
        "code": "T",  # Era TE
        "label": "Termometri", 
        "unit": "°C", 
        "threshold": 38.0 
    },
    "nivometria": {
        "code": "N",  # Era NI
        "label": "Nivometri", 
        "unit": "cm", 
        "threshold": 5.0 
    }
}

FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text.replace("\xa0", " ")).strip()

def parse_value(val_str):
    try:
        if not val_str: return None
        # Sostituisce virgola con punto
        clean = val_str.replace(",", ".").strip()
        # Cerca numeri (anche negativi e decimali)
        match = re.search(r'-?\d+(\.\d+)?', clean)
        if not match: return None
        return float(match.group(0))
    except:
        return None

def init_session():
    session = requests.Session()
    session.headers.update(FAKE_HEADERS)
    try:
        # Visita Home per cookie
        session.get(HOME_URL, timeout=15)
    except: pass
    return session

def scrape_sensor_type(session, sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"\n--- Analisi {config['label']} ({url}) ---")
    
    data_list = []
    
    try:
        r = session.get(url, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Cerca tutte le righe
        all_rows = soup.find_all("tr")
        print(f"📊 Righe HTML totali: {len(all_rows)}")

        for row in all_rows:
            cols = row.find_all(['td', 'th'])
            
            # Scarta righe troppo corte
            if len(cols) < 3: continue
            
            # Estrazione testi
            raw_cols = [clean_text(c.text) for c in cols]
            
            nome_stazione = raw_cols[0]
            data_ora = raw_cols[1]
            valore_raw = raw_cols[2]
            
            # FILTRI DI VALIDITA'
            # 1. Deve avere un nome sensato
            if not nome_stazione or "Stazione" in nome_stazione or "Provincia" in nome_stazione:
                continue
                
            # 2. La seconda colonna deve sembrare una data (contiene : o /)
            if ":" not in data_ora and "/" not in data_ora:
                continue

            # 3. La terza colonna deve essere un numero
            valore_num = parse_value(valore_raw)
            if valore_num is None:
                continue

            # ESTRAZIONE ID STAZIONE (Link)
            # Cerca il tag <a> nella prima colonna
            link_elem = cols[0].find("a")
            station_id = ""
            if link_elem and 'href' in link_elem.attrs:
                # Esempio href: stazione.php?id=653100
                match = re.search(r'id=(\d+)', link_elem['href'])
                if match:
                    station_id = match.group(1)

            # Calcolo stato allerta
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
        print(f"❌ Errore: {e}")

    print(f"✅ Record estratti: {len(data_list)}")
    return data_list

def main():
    session = init_session()
    
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

    # Se non abbiamo trovato nulla, c'è un problema grave
    if total_records == 0:
        print("⚠️ ATTENZIONE: 0 record totali trovati. Possibile cambio layout sito.")
    
    try:
        with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Salvataggio completato ({total_records} sensori totali)")
    except Exception as e:
        print(f"❌ Errore scrittura file: {e}")

if __name__ == "__main__":
    main()
