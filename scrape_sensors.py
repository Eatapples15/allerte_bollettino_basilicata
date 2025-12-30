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

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def scrape_category(driver, sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"📡 Acquisizione estesa: {config['label']}...")
    data_list = []
    
    try:
        driver.get(url)
        time.sleep(8) # Tempo aumentato per caricamento tabelle dinamiche
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            # Estrazione Nome Completo (include il tipo di sensore es. "Pioggia 1h")
            full_name = clean_text(cols[0].text)
            timestamp = clean_text(cols[1].text)
            valore_raw = clean_text(cols[3].text)

            if not full_name or valore_raw == "": continue

            # Determina il periodo/tipo dal testo
            periodo = "Istantaneo"
            for p in ["1h", "3h", "6h", "12h", "24h", "Raffica", "Scalare", "Vettoriale", "Direzione"]:
                if p.lower() in full_name.lower():
                    periodo = p
                    break

            # Gestione ID Stazione
            link = cols[0].find("a")
            station_id = ""
            if link and 'href' in link.attrs:
                id_match = re.search(r'id=(\d+)', link['href'])
                if id_match: station_id = id_match.group(1)

            # Parsing valore numerico (gestisce m/s, mm, ° e virgole)
            val_clean = valore_raw.replace(",", ".")
            num_match = re.search(r'[-+]?\d+(\.\d+)?', val_clean)
            valore_num = float(num_match.group(0)) if num_match else 0.0

            data_list.append({
                "id": station_id,
                "nome": full_name,
                "periodo": periodo,
                "valore": valore_raw, # Salviamo la stringa originale per unità di misura
                "valore_num": valore_num,
                "data": timestamp,
                "status": "alert" if valore_num >= config['threshold'] and "direzione" not in full_name.lower() else "normal"
            })
    except Exception as e:
        print(f"❌ Errore: {e}")
    
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
        print(f"✅ {config['label']}: {len(readings)} sensori letti.")

    driver.quit()

    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
    print(f"\n💾 JSON salvato correttamente.")

if __name__ == "__main__":
    main()
