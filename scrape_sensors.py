import json
import datetime
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# CONFIGURAZIONE
JSON_FILENAME = "dati_sensori.json"
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"

# Categorie incluse Nivometria (N) e Anemometria (VV)
SENSORI = {
    "pluviometria": {"code": "P", "label": "Pluviometri", "threshold": 40.0},
    "idrometria": {"code": "I", "label": "Idrometri", "threshold": 2.0},
    "termometria": {"code": "T", "label": "Termometri", "threshold": 38.0},
    "anemometria": {"code": "VV", "label": "Anemometri", "threshold": 15.0},
    "nivometria": {"code": "N", "label": "Nivometri", "threshold": 5.0}
}

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text.replace("\xa0", " ")).strip()

def parse_value(val_str):
    try:
        if not val_str: return 0.0
        clean = val_str.replace(",", ".")
        match = re.search(r'[-+]?\d+(\.\d+)?', clean)
        return float(match.group(0)) if match else 0.0
    except:
        return 0.0

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def scrape_category(driver, sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"📡 Acquisizione: {config['label']}...")
    data_list = []
    
    try:
        driver.get(url)
        time.sleep(7) # Tempo per il caricamento delle tabelle JS
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        all_rows = soup.find_all("tr")

        for row in all_rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            # Col 0: Stazione, Col 1: Ora, Col 2: Comune, Col 3: Valore
            nome_stazione = clean_text(cols[0].text)
            
            # Filtro per evitare di catturare righe di intestazione o errori di parsing
            if not nome_stazione or any(u in nome_stazione.lower() for u in ["mm", "°c", " m "]):
                continue

            valore_num = parse_value(cols[3].text)
            data_ora = clean_text(cols[1].text)

            # Estrazione ID Stazione dal link
            link = cols[0].find("a")
            station_id = ""
            if link and 'href' in link.attrs:
                match = re.search(r'id=(\d+)', link['href'])
                if match: station_id = match.group(1)

            # Fix Data breve (HH:mm -> DD/MM/YYYY HH:mm)
            if len(data_ora) <= 5 and ":" in data_ora:
                data_ora = f"{datetime.datetime.now().strftime('%d/%m/%Y')} {data_ora}"

            data_list.append({
                "id": station_id,
                "nome": nome_stazione,
                "valore": valore_num,
                "data": data_ora,
                "status": "alert" if valore_num >= config['threshold'] else "normal"
            })
    except Exception as e:
        print(f"❌ Errore su {sensor_key}: {e}")
    
    return data_list

def main():
    driver = setup_driver()
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    for key, config in SENSORI.items():
        readings = scrape_category(driver, key, config)
        final_data["sensori"][key] = {
            "meta": {"label": config['label'], "code": config['code']},
            "dati": readings
        }
        print(f"✅ {config['label']}: {len(readings)} record.")

    driver.quit()

    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
    print(f"\n💾 Database sensori aggiornato.")

if __name__ == "__main__":
    main()
