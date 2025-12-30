import json
import datetime
import re
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# --- CONFIGURAZIONE ---
JSON_FILENAME = "dati_sensori.json"
ANAGRAFICA_URL = "https://raw.githubusercontent.com/Eatapples15/allerte_bollettino_basilicata/main/anagrafica_stazioni.json"
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"

SENSORI = {
    "pluviometria": {"code": "P", "threshold": 40.0},
    "anemometria": {"code": "VV", "threshold": 15.0},
    "idrometria": {"code": "I", "threshold": 2.0},
    "termometria": {"code": "T", "threshold": 38.0},
    "nivometria": {"code": "N", "threshold": 5.0}
}

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def clean_station_name(text):
    """Pulisce il nome della stazione per il matching"""
    t = text.upper().split(' - ')[0].split(' (')[0]
    t = re.sub(r'\b(A|PRESSO|FIUME|TORRENTE|S\.)\b', '', t)
    return " ".join(t.split()).strip()

def scrape_category(driver, sensor_key, config, stazioni_map):
    url = f"{BASE_URL}?st={config['code']}"
    try:
        driver.get(url)
        time.sleep(8) 
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            raw_text = cols[0].get_text(separator=" ", strip=True)
            value_str = cols[3].get_text(strip=True)
            if not raw_text or value_str == "" or value_str == "-": continue

            # Matching con anagrafica
            clean_name = clean_station_name(raw_text)
            match_id = None
            
            # Cerca l'ID tra le parentesi nel testo originale o per nome pulito
            id_in_text = re.search(r'\((\d+)\)', raw_text)
            if id_in_text:
                match_id = id_in_text.group(1)
            else:
                # Fallback: cerca per nome pulito nell'anagrafica
                for sid, info in stazioni_map.items():
                    if clean_name in info['nome_anagrafica']:
                        match_id = sid
                        break

            if not match_id or match_id not in stazioni_map: continue

            target = stazioni_map[match_id]["dati"]
            low_txt = raw_text.lower()

            # Estrazione numerica per allerta
            val_num = 0.0
            try:
                val_num = float(value_str.replace(",", ".").replace(" mm", "").replace(" m", "").replace(" °C", "").split()[0])
            except: pass

            # Organizzazione specifica per tipo
            if sensor_key == "pluviometria":
                label = "ist"
                if "1 ora" in low_txt or "1h" in low_txt: label = "h1"
                elif "3 ore" in low_txt or "3h" in low_txt: label = "h3"
                elif "6 ore" in low_txt or "6h" in low_txt: label = "h6"
                elif "12 ore" in low_txt or "12h" in low_txt: label = "h12"
                elif "24 ore" in low_txt or "24h" in low_txt: label = "h24"
                elif "cumulate" in low_txt: label = "cum"
                target["pioggia"][label] = value_str
                if val_num >= config['threshold'] and label in ["h1", "h24"]: stazioni_map[match_id]["alert"] = True

            elif sensor_key == "idrometria":
                target["idro"] = value_str
                if val_num >= config['threshold']: stazioni_map[match_id]["alert"] = True

            elif sensor_key == "anemometria":
                if "raffica" in low_txt and "direzione" not in low_txt:
                    target["vento_vel"] = value_str
                    if val_num >= config['threshold']: stazioni_map[match_id]["alert"] = True
                elif "raffica" in low_txt and "direzione" in low_txt:
                    target["vento_dir"] = value_str

            elif sensor_key == "termometria": target["temp"] = value_str
            elif sensor_key == "nivometria": target["neve"] = value_str

    except Exception as e: print(f"Errore {sensor_key}: {e}")

def main():
    # 1. Carica Anagrafica
    r = requests.get(ANAGRAFICA_URL)
    anagrafica = r.json()
    stazioni_map = {}
    for a in anagrafica:
        stazioni_map[str(a['id'])] = {
            "id": a['id'],
            "nome": "", # Verrà popolato dallo scrape
            "nome_anagrafica": a.get('stazione', '').upper(),
            "lat": a['lat'],
            "lon": a['lon'],
            "alert": False,
            "dati": {
                "pioggia": {}, "idro": None, "temp": None, 
                "vento_vel": None, "vento_dir": None, "neve": None
            }
        }

    # 2. Avvia Selenium
    driver = setup_driver()
    for key, config in SENSORI.items():
        scrape_category(driver, key, config, stazioni_map)
    driver.quit()

    # 3. Filtra solo stazioni con dati e salva
    final_list = []
    for sid, data in stazioni_map.items():
        # Verifichiamo se ci sono dati reali (non None o dizionari vuoti)
        has_data = any([data["dati"]["pioggia"], data["dati"]["idro"], data["dati"]["temp"], data["dati"]["vento_vel"]])
        if has_data:
            final_list.append(data)

    output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "stazioni": final_list
    }

    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

if __name__ == "__main__": main()
