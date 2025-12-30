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
    "idrometria": {"code": "I", "threshold": 2.0},
    "termometria": {"code": "T", "threshold": 38.0},
    "anemometria": {"code": "VV", "threshold": 15.0},
    "nivometria": {"code": "N", "threshold": 5.0}
}

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text.replace("\xa0", " ")).strip()

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def scrape_category(driver, sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    # Usiamo un dizionario per raggruppare i sensori multipli della stessa stazione
    grouped_data = {}
    
    try:
        driver.get(url)
        time.sleep(7)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            raw_full_text = clean_text(cols[0].text)
            if not raw_full_text or any(u in raw_full_text.lower() for u in ["mm", "°c"]): continue

            # Estrazione Nome e ID
            st_name = raw_full_text.split(' - ')[0].split(' (')[0].strip().upper()
            link = cols[0].find("a")
            st_id = ""
            if link and 'href' in link.attrs:
                m = re.search(r'id=(\d+)', link['href'])
                if m: st_id = m.group(1)
            
            if not st_id: continue

            valore_str = clean_text(cols[3].text)
            
            if st_id not in grouped_data:
                grouped_data[st_id] = {
                    "id": st_id,
                    "nome": st_name,
                    "valore": valore_str, # Il primo valore trovato (solitamente istantaneo o cumulata)
                    "serie": [],
                    "data": clean_text(cols[1].text)
                }
            
            # Aggiungiamo il valore alla serie (utile per pluviometria: ist, 1h, 3h, 6h, 12h, 24h)
            grouped_data[st_id]["serie"].append(valore_str)

    except Exception as e:
        print(f"Errore su {sensor_key}: {e}")
    
    return list(grouped_data.values())

def main():
    driver = setup_driver()
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    for key, config in SENSORI.items():
        final_data["sensori"][key] = {"dati": scrape_category(driver, key, config)}

    driver.quit()
    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main()
