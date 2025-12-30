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

# --- CONFIGURAZIONE ---
JSON_FILENAME = "dati_sensori.json"
ANAGRAFICA_URL = "https://raw.githubusercontent.com/Eatapples15/allerte_bollettino_basilicata/main/anagrafica_stazioni.json"
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

def normalize_name(text):
    """Semplifica il nome per il matching (es: 'Agri a Roccanova' -> 'roccanova')"""
    if not text: return ""
    t = text.lower()
    t = t.replace("fiume", "").replace("torrente", "").replace("canale", "")
    t = t.replace(" a ", " ").replace(" presso ", " ").replace(" in ", " ")
    t = re.sub(r'[^a-z0-9 ]', '', t) # Rimuove punteggiatura
    return t.strip()

def scrape():
    # 1. Carica Anagrafica
    try:
        r_ana = requests.get(ANAGRAFICA_URL)
        anagrafica_raw = r_ana.json()
    except:
        anagrafica_raw = []
    
    # Prepariamo l'indice dell'anagrafica
    stazioni_finali = {}

    driver = setup_driver()
    
    for cat, config in SENSORI.items():
        try:
            print(f"Scraping {cat}...")
            driver.get(f"{BASE_URL}?st={config['code']}")
            time.sleep(6) # Tempo per caricamento tabelle dinamiche
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            rows = soup.find_all("tr")
            
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 4: continue
                
                raw_full_name = cols[0].get_text(strip=True)
                valore_str = cols[3].get_text(strip=True)
                
                if not raw_full_name or valore_str in ["", "-", "n.d."]: continue

                # Cerchiamo il miglior match nell'anagrafica
                found_id = None
                norm_site = normalize_name(raw_full_name)
                
                # Prova 1: Match per ID nel testo (se presente)
                id_match = re.search(r'\((\d+)\)', raw_full_name)
                if id_match:
                    found_id = id_match.group(1)
                
                # Prova 2: Match per nome incrociato
                if not found_id:
                    for a in anagrafica_raw:
                        norm_ana = normalize_name(a.get('stazione', ''))
                        if norm_ana in norm_site or norm_site in norm_ana:
                            found_id = str(a['id'])
                            break

                # Se non troviamo match, usiamo il nome normalizzato come ID temporaneo
                station_key = found_id if found_id else f"TEMP_{norm_site}"

                if station_key not in stazioni_finali:
                    # Recupera dati geografici se presenti
                    geo = next((a for a in anagrafica_raw if str(a['id']) == found_id), None)
                    stazioni_finali[station_key] = {
                        "id": found_id if found_id else "N/D",
                        "nome": raw_full_name.split('-')[0].split('(')[0].strip().upper(),
                        "lat": geo['lat'] if geo else None,
                        "lon": geo['lon'] if geo else None,
                        "alert": False,
                        "dati": {"pioggia": {}, "idro": None, "temp": None, "vento": None}
                    }

                # Inserimento Dati
                st = stazioni_finali[station_key]
                low_n = raw_full_name.lower()
                
                if cat == "pluviometria":
                    if "1 ora" in low_n or "1h" in low_n: st["dati"]["pioggia"]["h1"] = valore_str
                    elif "3 ore" in low_n or "3h" in low_n: st["dati"]["pioggia"]["h3"] = valore_str
                    elif "6 ore" in low_n or "6h" in low_n: st["dati"]["pioggia"]["h6"] = valore_str
                    elif "12 ore" in low_n or "12h" in low_n: st["dati"]["pioggia"]["h12"] = valore_str
                    elif "24 ore" in low_n or "24h" in low_n: st["dati"]["pioggia"]["h24"] = valore_str
                    elif "cumulate" in low_n: st["dati"]["pioggia"]["cum"] = valore_str
                
                elif cat == "idrometria":
                    st["dati"]["idro"] = valore_str
                
                elif cat == "termometria":
                    st["dati"]["temp"] = valore_str
                
                elif cat == "anemometria" and "raffica" in low_n and "direzione" not in low_n:
                    st["dati"]["vento"] = valore_str

        except Exception as e:
            print(f"Errore {cat}: {e}")

    driver.quit()

    # Rimuovi stazioni senza dati significativi e salva
    final_output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "stazioni": [s for s in stazioni_finali.values() if any(s["dati"].values())]
    }

    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    scrape()
