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

# Mappa categorie: Label JSON -> Codice Sito -> Soglia di alert generica
SENSORI = {
    "pluviometria": {"code": "P", "label": "Pluviometri", "unit": "mm", "threshold": 40.0},
    "idrometria": {"code": "I", "label": "Idrometri", "unit": "m", "threshold": 2.0},
    "termometria": {"code": "T", "label": "Termometri", "unit": "°C", "threshold": 38.0},
    "anemometria": {"code": "VV", "label": "Anemometri", "unit": "m/s", "threshold": 15.0},
    "nivometria": {"code": "N", "label": "Nivometri", "unit": "cm", "threshold": 5.0}
}

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text.replace("\xa0", " ")).strip()

def parse_value(val_str):
    try:
        if not val_str: return None
        clean = val_str.replace(",", ".")
        match = re.search(r'-?\d+(\.\d+)?', clean)
        return float(match.group(0)) if match else None
    except:
        return None

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def scrape_with_selenium(driver, sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"📡 Navigazione: {config['label']}...")
    data_list = []
    
    try:
        driver.get(url)
        time.sleep(6) # Tempo per il caricamento del JS regionale
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        all_rows = soup.find_all("tr")

        for row in all_rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            raw_cols = [clean_text(c.text) for c in cols]
            nome_stazione = raw_cols[0]
            
            # Filtro nomi validi
            if not nome_stazione or "Stazione" in nome_stazione: continue
            if any(u in nome_stazione.lower() for u in ["mm", " m", "°c"]): continue

            valore_num = parse_value(raw_cols[3])
            data_ora = raw_cols[4] if len(raw_cols) > 4 else ""

            if valore_num is None: continue

            # Estrazione ID
            link = cols[0].find("a")
            station_id = ""
            if link and 'href' in link.attrs:
                match = re.search(r'id=(\d+)', link['href'])
                if match: station_id = match.group(1)

            # Fix Data
            if len(data_ora) <= 5 and ":" in data_ora:
                data_ora = f"{datetime.datetime.now().strftime('%d/%m/%Y')} {data_ora}"

            status = "normal"
            if abs(valore_num) >= config['threshold']: status = "alert"

            data_list.append({
                "id": station_id,
                "nome": nome_stazione,
                "valore": valore_num,
                "data": data_ora,
                "status": status,
                "tipo": config['label']
            })
    except Exception as e:
        print(f"❌ Errore Selenium su {sensor_key}: {e}")
    
    return data_list

def main():
    driver = setup_driver()
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    total = 0
    try:
        for key, config in SENSORI.items():
            readings = scrape_with_selenium(driver, key, config)
            final_data["sensori"][key] = { "meta": config, "dati": readings }
            total += len(readings)
            print(f"✅ Estratti {len(readings)} record per {key}")
    finally:
        driver.quit()

    try:
        with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Salvataggio completato ({total} sensori live)")
    except Exception as e:
        print(f"❌ Errore scrittura file: {e}")

if __name__ == "__main__":
    main()
