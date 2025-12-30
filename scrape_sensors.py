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
            
            raw_full_text = " ".join(cols[0].get_text(separator=" ", strip=True).split())
            timestamp = cols[1].get_text(strip=True)
            value_str = cols[3].get_text(strip=True)
            
            if not raw_full_text or value_str == "": continue

            # --- ESTRAZIONE NOME STAZIONE ---
            st_name = raw_full_text.split(' - ')[0].split(' (')[0].strip()

            # --- ESTRAZIONE PERIODO/TIPO SENSORI ---
            label = "Dato"
            text_lower = raw_full_text.lower()
            
            # Logica Pioggia
            if sensor_key == "pluviometria":
                if "1 ora" in text_lower or "1h" in text_lower: label = "t1"
                elif "3 ore" in text_lower or "3h" in text_lower: label = "t3"
                elif "6 ore" in text_lower or "6h" in text_lower: label = "t6"
                elif "12 ore" in text_lower or "12h" in text_lower: label = "t12"
                elif "24 ore" in text_lower or "24h" in text_lower: label = "t24"
                elif "cumulate" in text_lower: label = "Cumulata"
                else: label = "Istantaneo"
            
            # Logica Vento
            elif sensor_key == "anemometria":
                if "vettoriale" in text_lower:
                    label = "DIR VETT" if "direzione" in text_lower else "VEL VETT"
                elif "scalare" in text_lower:
                    label = "DIR SCAL" if "direzione" in text_lower else "VEL SCAL"
                elif "raffica" in text_lower:
                    label = "DIR RAFF" if "direzione" in text_lower else "VEL RAFF"

            # Logica Altri
            elif sensor_key == "termometria": label = "TEMP"
            elif sensor_key == "idrometria": label = "IDRO"
            elif sensor_key == "nivometria": label = "NEVE"

            # --- LOGICA ALERT ---
            val_clean = value_str.replace(",", ".")
            num_match = re.search(r'[-+]?\d+(\.\d+)?', val_clean)
            valore_num = float(num_match.group(0)) if num_match else 0.0

            is_alert = False
            # Alert attivo solo se NON è una direzione (gradi) e supera la soglia
            if "DIR" not in label and "°" not in value_str:
                if valore_num >= config['threshold']:
                    is_alert = True

            data_list.append({
                "stazione": st_name,
                "sensore": label,
                "valore": value_str,
                "orario": timestamp,
                "status": "alert" if is_alert else "normal"
            })
    except Exception as e: print(f"Errore: {e}")
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
