import json
import datetime
import re
import time
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# CONFIGURAZIONE
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"
DETTAGLIO_URL = "https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php"
NUM_WORKERS = 5 

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--blink-settings=imagesEnabled=false")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

drivers = [create_driver() for _ in range(NUM_WORKERS)]

def get_station_history(index, station_id, station_name):
    """Estrae lo storico reale dalla tabella di dettaglio"""
    driver = drivers[index % NUM_WORKERS]
    try:
        driver.get(f"{DETTAGLIO_URL}?id={station_id}")
        time.sleep(2) # Attesa per render tabella storica
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Seleziona le celle dei valori (solitamente la seconda colonna)
        # Cerchiamo tutti i <td> che contengono numeri
        rows = soup.find_all("tr")[1:] # Salta header
        history = []
        for r in rows:
            tds = r.find_all("td")
            if len(tds) >= 2:
                val_text = tds[1].get_text(strip=True).replace(",", ".")
                try:
                    val = float(re.findall(r"[-+]?\d*\.\d+|\d+", val_text)[0])
                    history.append(val)
                except: continue
        
        return {
            "id": station_id,
            "nome": station_name,
            "valore": history[0] if history else 0,
            "dati_multipli": {
                "1h": round(sum(history[:4]), 1) if len(history) >= 4 else (history[0] if history else 0),
                "3h": round(sum(history[:12]), 1) if len(history) >= 12 else 0,
                "6h": round(sum(history[:24]), 1) if len(history) >= 24 else 0,
                "12h": round(sum(history[:48]), 1) if len(history) >= 48 else 0,
                "24h": round(sum(history[:96]), 1) if len(history) >= 96 else 0
            }
        }
    except:
        return {"id": station_id, "nome": station_name, "valore": 0, "dati_multipli": {"1h":0,"3h":0,"6h":0,"12h":0,"24h":0}}

def scrape_category(code):
    """Ottiene l'elenco stazioni pulito"""
    driver = drivers[0]
    driver.get(f"{BASE_URL}?st={code}")
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    stations = []
    # Cerchiamo solo i link che hanno un ID e il testo della stazione
    links = soup.find_all("a", href=re.compile(r"id=\d+"))
    for a in links:
        sid = re.search(r'id=(\d+)', a['href']).group(1)
        name = a.get_text(strip=True)
        # Evita che il valore (es 7.2mm) venga preso come nome
        if sid and name and not any(x in name.lower() for x in ["mm", " m", "°c"]):
            stations.append((sid, name))
    
    return list(set(stations)) # Rimuove duplicati

def main():
    start_time = time.time()
    
    # 1. Elenco pulito
    pluvio_list = scrape_category("P")
    idro_list = scrape_category("I")
    
    print(f"✅ Basi trovate: {len(pluvio_list)} Pluvio, {len(idro_list)} Idro")

    # 2. Parallelizzazione Pluviometri (Storico)
    results_p = []
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [executor.submit(get_station_history, i, s[0], s[1]) for i, s in enumerate(pluvio_list)]
        results_p = [f.result() for f in futures]

    # 3. Parallelizzazione Idrometri (Solo valore istantaneo per velocità)
    results_i = []
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [executor.submit(get_station_history, i, s[0], s[1]) for i, s in enumerate(idro_list)]
        results_i = [f.result() for f in futures]

    output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {
            "pluviometria": {"meta": {"label": "Pluviometri", "unit": "mm"}, "dati": results_p},
            "idrometria": {"meta": {"label": "Idrometri", "unit": "m"}, "dati": results_i}
        }
    }

    with open("dati_sensori.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    for d in drivers: d.quit()
    print(f"🎉 Fine. Processate {len(results_p) + len(results_i)} basi in {round(time.time()-start_time)}s")

if __name__ == "__main__":
    main()
