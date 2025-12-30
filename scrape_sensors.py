import json
import datetime
import re
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By

JSON_FILENAME = "dati_sensori.json"
ANAGRAFICA_URL = "https://raw.githubusercontent.com/Eatapples15/allerte_bollettino_basilicata/main/anagrafica_stazioni.json"
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"

# Configurazione sensori
SENSORI = {
    "pluviometria": {"code": "P"},
    "anemometria": {"code": "VV"},
    "idrometria": {"code": "I"},
    "termometria": {"code": "T"}
}

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def super_clean(text):
    if not text: return ""
    t = text.upper()
    t = re.sub(r'\b(A|IN|PRESSO|FIUME|TORRENTE|CANALE|S\.|SAN|SS\d+)\b', '', t)
    t = re.sub(r'[^A-Z0-9]', '', t)
    return t.strip()

def scrape():
    try:
        r_ana = requests.get(ANAGRAFICA_URL)
        anagrafica_raw = r_ana.json()
    except:
        print("Errore caricamento anagrafica")
        return

    stazioni_finali = {}
    driver = setup_driver()
    
    for cat, config in SENSORI.items():
        try:
            print(f"Scraping integrale {cat}...")
            driver.get(f"{BASE_URL}?st={config['code']}")
            time.sleep(5)

            # FORZA IL CARICAMENTO DI TUTTE LE RIGHE (Importante!)
            try:
                # Cerca il selettore "Mostra X voci" (solitamente DataTables usa 'length')
                select_element = driver.find_element(By.NAME, "DataTables_Table_0_length")
                select = Select(select_element)
                select.select_by_value("-1") # -1 solitamente indica "Tutte"
                time.sleep(3)
            except:
                print(f"Selettore 'Tutte' non trovato per {cat}, procedo con vista standard.")

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            table = soup.find("table")
            if not table: continue
            
            rows = table.find_all("tr")
            print(f"Trovate {len(rows)} righe per {cat}")

            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 4: continue
                
                raw_full_name = cols[0].get_text(strip=True)
                valore_str = cols[3].get_text(strip=True)
                
                if not raw_full_name or valore_str in ["", "-", "n.d."]: continue

                # Matching ID o Nome
                found_id = None
                id_match = re.search(r'\((\d+)\)', raw_full_name)
                if id_match: found_id = id_match.group(1)
                
                norm_site = super_clean(raw_full_name)
                if not found_id:
                    for a in anagrafica_raw:
                        if super_clean(a.get('stazione','')) in norm_site:
                            found_id = str(a['id'])
                            break

                station_key = found_id if found_id else f"ERR_{norm_site}"

                if station_key not in stazioni_finali:
                    geo = next((a for a in anagrafica_raw if str(a['id']) == found_id), None)
                    stazioni_finali[station_key] = {
                        "id": found_id,
                        "nome": raw_full_name.split('(')[0].strip().upper(),
                        "lat": geo['lat'] if geo else None,
                        "lon": geo['lon'] if geo else None,
                        "dati": {"pioggia": {}, "idro": None, "temp": None, "vento": None}
                    }

                st = stazioni_finali[station_key]
                low_n = raw_full_name.lower()
                
                if cat == "pluviometria":
                    if "1 ora" in low_n or "1h" in low_n: st["dati"]["pioggia"]["h1"] = valore_str
                    elif "24 ore" in low_n or "24h" in low_n: st["dati"]["pioggia"]["h24"] = valore_str
                elif cat == "idrometria": st["dati"]["idro"] = valore_str
                elif cat == "termometria": st["dati"]["temp"] = valore_str
                elif cat == "anemometria": st["dati"]["vento"] = valore_str

        except Exception as e:
            print(f"Errore durante {cat}: {e}")

    driver.quit()

    output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "stazioni": list(stazioni_finali.values())
    }

    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    print(f"Scraping completato: {len(stazioni_finali)} stazioni salvate.")

if __name__ == "__main__":
    scrape()
