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
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"
JSON_FILENAME = "dati_sensori.json"

# Soglie fisse da PDF per validazione rapida nello scraping [cite: 2, 11]
SOGLIE_IDRO = {"647100": 4.0, "179800": 3.5, "387900": 1.2} 

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def get_multi_hour_data(driver, station_id):
    """
    Simula l'estrazione degli accumuli temporali. 
    In un ambiente reale, questa funzione navigherebbe nel dettaglio della stazione
    per sommare i millimetri registrati negli intervalli precedenti.
    """
    # Placeholder per logica di calcolo cumulati basata su storico 24h
    return {
        "1h": 0.0,
        "3h": 0.0,
        "6h": 0.0,
        "12h": 0.0,
        "24h": 0.0
    }

def scrape_sensors():
    driver = setup_driver()
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {
            "idrometria": {"meta": {"label": "Idrometri", "unit": "m"}, "dati": []},
            "pluviometria": {"meta": {"label": "Pluviometri", "unit": "mm"}, "dati": []}
        }
    }

    codes = {"idrometria": "I", "pluviometria": "P"}

    for key, code in codes.items():
        driver.get(f"{BASE_URL}?st={code}")
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            name = cols[0].get_text(strip=True)
            val_raw = cols[3].get_text(strip=True).replace(",", ".")
            try:
                val = float(re.findall(r"[-+]?\d*\.\d+|\d+", val_raw)[0])
            except: continue

            link = cols[0].find("a")
            sid = re.search(r'id=(\d+)', link['href']).group(1) if link else ""

            entry = {
                "id": sid,
                "nome": name,
                "valore": val,
                "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                "status": "normal"
            }

            # Logica specifica per Pluviometri: Accumuli Multi-ora 
            if key == "pluviometria":
                entry["dati_multipli"] = get_multi_hour_data(driver, sid)
                # Esempio: se valore istantaneo > 0, popola fittiziamente per test dashboard
                entry["dati_multipli"]["1h"] = val 
            
            # Logica soglie Idrometriche [cite: 11, 15]
            if key == "idrometria" and sid in SOGLIE_IDRO:
                if val >= SOGLIE_IDRO[sid]: entry["status"] = "alert"

            final_data["sensori"][key]["dati"].append(entry)

    driver.quit()
    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    scrape_sensors()
