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
    "termometria": {"code": "T", "label": "Termometri", "threshold": 38.0}
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
            
            full_text = " ".join(cols[0].get_text(separator=" ", strip=True).split())
            timestamp = cols[1].get_text(strip=True)
            value_str = cols[3].get_text(strip=True)
            if not full_text or value_str == "": continue

            # LOGICA PIOGGIA: t1, t3, t6, t12, t24
            periodo = "Istantaneo"
            if config['code'] == "P":
                if " 1h" in full_text: periodo = "t1"
                elif " 3h" in full_text: periodo = "t3"
                elif " 6h" in full_text: periodo = "t6"
                elif " 12h" in full_text: periodo = "t12"
                elif " 24h" in full_text: periodo = "t24"
                elif "Cumulata" in full_text: periodo = "Cumulata"
            
            # LOGICA VENTO
            elif config['code'] == "VV":
                if "Vettoriale" in full_text and "Velocità" in full_text: periodo = "VEL VETT"
                elif "Vettoriale" in full_text and "Direzione" in full_text: periodo = "DIR VETT"
                elif "Scalare" in full_text and "Velocità" in full_text: periodo = "VEL SCAL"
                elif "Scalare" in full_text and "Direzione" in full_text: periodo = "DIR SCAL"
                elif "Raffica" in full_text and "Velocità" in full_text: periodo = "VEL RAFF"
                elif "Raffica" in full_text and "Direzione" in full_text: periodo = "DIR RAFF"

            # Pulizia Nome Stazione
            st_name = full_text.split(' - ')[0].split(' (')[0]
            for term in ["Velocità", "Direzione", "Vento", "Vettoriale", "Scalare", "Raffica", "Pioggia", "1h", "3h", "6h", "12h", "24h", "Cumulata"]:
                st_name = st_name.replace(term, "")
            st_name = st_name.strip()

            val_clean = value_str.replace(",", ".")
            num_match = re.search(r'[-+]?\d+(\.\d+)?', val_clean)
            valore_num = float(num_match.group(0)) if num_match else 0.0

            # ALERT SOLO SU VELOCITÀ E PIOGGIA, NO GRADI
            is_alert = False
            if valore_num >= config['threshold']:
                if config['code'] == "P" or (config['code'] == "VV" and "VEL" in periodo):
                    is_alert = True

            data_list.append({
                "stazione": st_name,
                "periodo": periodo,
                "valore": value_str,
                "data": timestamp,
                "status": "alert" if is_alert else "normal"
            })
    except Exception as e: print(f"Errore: {e}")
    return data_list

def main():
    driver = setup_driver()
    final_data = {"ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "sensori": {}}
    for key, config in SENSORI.items():
        final_data["sensori"][key] = {"meta": {"label": config['label'], "code": config['code']}, "dati": scrape_category(driver, key, config)}
    driver.quit()
    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__": main()
