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
    "pluviometria": {"code": "P", "label": "Pluviometri", "threshold": 40.0},
    "anemometria": {"code": "VV", "label": "Anemometri", "threshold": 15.0},
    "idrometria": {"code": "I", "label": "Idrometri", "threshold": 2.0},
    "termometria": {"code": "T", "label": "Termometri", "threshold": 38.0},
    "nivometria": {"code": "N", "label": "Nivometri", "threshold": 5.0}
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
    print(f"📡 Scansione parametri avanzati per {config['label']}...")
    data_list = []
    
    try:
        driver.get(url)
        time.sleep(10) 
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            full_text = " ".join(cols[0].get_text(separator=" ", strip=True).split())
            timestamp = cols[1].get_text(strip=True)
            value_str = cols[3].get_text(strip=True)

            if not full_text or value_str == "": continue

            # LOGICA DI RICONOSCIMENTO PARAMETRI VENTO
            periodo = "Istantaneo"
            if config['code'] == "VV":
                if "Velocità Vento Vettoriale" in full_text: periodo = "VEL VETT"
                elif "Direzione Vento Vettoriale" in full_text: periodo = "DIR VETT"
                elif "Velocità Vento Scalare" in full_text: periodo = "VEL SCAL"
                elif "Direzione Vento Scalare" in full_text: periodo = "DIR SCAL"
                elif "Velocità Vento Raffica" in full_text: periodo = "RAFFICA"
                elif "Direzione Vento Raffica" in full_text: periodo = "DIR RAFF"
            
            # LOGICA PIOGGIA
            elif config['code'] == "P":
                if "1h" in full_text: periodo = "1h"
                elif "3h" in full_text: periodo = "3h"
                elif "6h" in full_text: periodo = "6h"
                elif "12h" in full_text: periodo = "12h"
                elif "24h" in full_text: periodo = "24h"
                else: periodo = "Cumulata"

            # Pulizia Nome Stazione
            st_name = full_text.split(' - ')[0].split(' (')[0]
            for term in ["Velocità", "Direzione", "Vento", "Vettoriale", "Scalare", "Raffica", "Pioggia", "1h", "3h", "6h", "12h", "24h"]:
                st_name = st_name.replace(term, "")
            st_name = st_name.strip()

            val_clean = value_str.replace(",", ".")
            num_match = re.search(r'[-+]?\d+(\.\d+)?', val_clean)
            valore_num = float(num_match.group(0)) if num_match else 0.0

            data_list.append({
                "stazione": st_name,
                "periodo": periodo,
                "valore": value_str,
                "valore_num": valore_num,
                "data": timestamp,
                "status": "alert" if (valore_num >= config['threshold'] and "DIR" not in periodo) else "normal"
            })
    except Exception as e:
        print(f"❌ Errore: {e}")
    
    return data_list

def main():
    driver = setup_driver()
    final_data = {"ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "sensori": {}}
    for key, config in SENSORI.items():
        readings = scrape_category(driver, key, config)
        final_data["sensori"][key] = {"meta": {"label": config['label'], "code": config['code']}, "dati": readings}
    driver.quit()
    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main()
