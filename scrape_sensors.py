import json
import datetime
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

JSON_FILENAME = "dati_sensori.json"
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
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def scrape_category(driver, sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    data_list = []
    try:
        driver.get(url)
        time.sleep(10) 
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            # Testo integrale della prima colonna (es: "Castelsaraceno - Velocità vento raffica")
            raw_name = " ".join(cols[0].get_text(separator=" ", strip=True).split())
            timestamp = cols[1].get_text(strip=True)
            value_str = cols[3].get_text(strip=True)
            
            if not raw_name or value_str == "": continue

            # Estrazione Nome Stazione (Prima parte della stringa)
            st_name = raw_name.split(' - ')[0].split(' (')[0].strip()
            
            # Identificazione del Tipo di Sensore (Seconda parte della stringa)
            # Se non c'è il trattino, usiamo il nome intero
            sensor_type = raw_name.replace(st_name, "").replace("-", "").strip()
            if not sensor_type: sensor_type = "Istantaneo"

            val_clean = value_str.replace(",", ".")
            num_match = re.search(r'[-+]?\d+(\.\d+)?', val_clean)
            valore_num = float(num_match.group(0)) if num_match else 0.0

            # Alert logic (escludendo le direzioni in gradi)
            is_alert = False
            if valore_num >= config['threshold'] and "direzione" not in raw_name.lower() and "grado" not in raw_name.lower():
                is_alert = True

            data_list.append({
                "stazione": st_name,
                "sensore": sensor_type,
                "valore": value_str,
                "valore_num": valore_num,
                "orario": timestamp,
                "status": "alert" if is_alert else "normal"
            })
    except Exception as e: print(f"Errore su {sensor_key}: {e}")
    return data_list

def main():
    driver = setup_driver()
    final_data = {"ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "sensori": {}}
    for key, config in SENSORI.items():
        final_data["sensori"][key] = {"dati": scrape_category(driver, key, config)}
    driver.quit()
    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__": main()
