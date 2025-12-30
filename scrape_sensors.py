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
    chrome_options.add_argument("--disable-dev-shm-usage")
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
            
            raw_full_text = " ".join(cols[0].get_text(separator=" ", strip=True).split())
            timestamp = cols[1].get_text(strip=True)
            value_str = cols[3].get_text(strip=True)
            
            if not raw_full_text or value_str == "": continue

            # Estrazione Stazione
            st_name = raw_full_text.split(' - ')[0].split(' (')[0].strip()

            # Mappatura Etichette
            label = "Dato"
            low_txt = raw_full_text.lower()
            
            if sensor_key == "pluviometria":
                if "1 ora" in low_txt or "1h" in low_txt: label = "t1"
                elif "3 ore" in low_txt or "3h" in low_txt: label = "t3"
                elif "6 ore" in low_txt or "6h" in low_txt: label = "t6"
                elif "12 ore" in low_txt or "12h" in low_txt: label = "t12"
                elif "24 ore" in low_txt or "24h" in low_txt: label = "t24"
                elif "cumulate" in low_txt: label = "Cumulata"
                else: label = "Ist."
            
            elif sensor_key == "anemometria":
                if "vettoriale" in low_txt: label = "DIR VETT" if "direzione" in low_txt else "VEL VETT"
                elif "scalare" in low_txt: label = "DIR SCAL" if "direzione" in low_txt else "VEL SCAL"
                elif "raffica" in low_txt: label = "DIR RAFF" if "direzione" in low_txt else "VEL RAFF"
            
            elif sensor_key == "termometria": label = "TEMP"
            elif sensor_key == "idrometria": label = "IDRO"
            elif sensor_key == "nivometria": label = "NEVE"

            # Logica Allerta (Esclude Gradi e Direzioni)
            val_clean = value_str.replace(",", ".")
            num_match = re.search(r'[-+]?\d+(\.\d+)?', val_clean)
            valore_num = float(num_match.group(0)) if num_match else 0.0

            is_alert = False
            if valore_num >= config['threshold'] and "DIR" not in label and "°" not in value_str:
                is_alert = True

            data_list.append({
                "stazione": st_name,
                "sensore": label,
                "valore": value_str, # Contiene già l'unità di misura dal sito
                "orario": timestamp,
                "status": "alert" if is_alert else "normal"
            })
    except Exception as e: print(f"Errore {sensor_key}: {e}")
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
