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
NUM_WORKERS = 5 # Numero di browser aperti contemporaneamente

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--blink-settings=imagesEnabled=false") # Velocizza non caricando immagini
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Inizializziamo un pool di driver per i thread
drivers = [create_driver() for _ in range(NUM_WORKERS)]

def get_station_data(index, station_id, station_name):
    """Estrae lo storico usando uno dei driver del pool"""
    driver = drivers[index % NUM_WORKERS]
    try:
        driver.get(f"{DETTAGLIO_URL}?id={station_id}")
        time.sleep(1.5) # Attesa minima per render tabella
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Estrazione valori dalla tabella storica
        rows = soup.select("table tr")[1:] # Seleziona righe saltando header
        rain_values = []
        for r in rows:
            tds = r.find_all("td")
            if len(tds) >= 2:
                try:
                    val = float(tds[1].get_text(strip=True).replace(",", "."))
                    rain_values.append(val)
                except: continue
        
        # Calcolo somme mobili (basate su step 15 min - dati forniti da PDF) 
        return {
            "id": station_id,
            "nome": station_name,
            "valore": rain_values[0] if rain_values else 0,
            "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "status": "normal",
            "dati_multipli": {
                "1h": round(sum(rain_values[:4]), 1) if len(rain_values) >= 4 else 0,
                "3h": round(sum(rain_values[:12]), 1) if len(rain_values) >= 12 else 0,
                "6h": round(sum(rain_values[:24]), 1) if len(rain_values) >= 24 else 0,
                "12h": round(sum(rain_values[:48]), 1) if len(rain_values) >= 48 else 0,
                "24h": round(sum(rain_values[:96]), 1) if len(rain_values) >= 96 else 0
            }
        }
    except Exception as e:
        return {"id": station_id, "nome": station_name, "valore": 0, "status": "error", "dati_multipli": {}}

def main():
    start_time = time.time()
    print(f"⏳ Avvio acquisizione con {NUM_WORKERS} browser paralleli...")

    # 1. Recupero elenco iniziale dei pluviometri
    main_driver = drivers[0]
    main_driver.get(f"{BASE_URL}?st=P")
    time.sleep(4) # Importante per caricamento JS iniziale
    soup = BeautifulSoup(main_driver.page_source, 'html.parser')
    
    links = soup.select('a[href*="id="]')
    stations_to_do = []
    for a in links:
        sid = re.search(r'id=(\d+)', a['href']).group(1)
        sname = a.get_text(strip=True)
        if sid and sname:
            stations_to_do.append((sid, sname))
    
    stations_to_do = list(set(stations_to_do)) # Rimuove duplicati
    print(f"✅ Trovate {len(stations_to_do)} stazioni pluviometriche.")

    # 2. Elaborazione parallela
    final_readings = []
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [executor.submit(get_station_data, i, s[0], s[1]) for i, s in enumerate(stations_to_do)]
        for future in futures:
            final_readings.append(future.result())

    # 3. Salvataggio
    output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {
            "pluviometria": {"meta": {"label": "Pluviometri", "unit": "mm"}, "dati": final_readings},
            "idrometria": {"meta": {"label": "Idrometri", "unit": "m"}, "dati": []} # Aggiungibile con logica simile
        }
    }

    with open("dati_sensori.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    # Pulizia driver
    for d in drivers: d.quit()
    
    end_time = time.time()
    print(f"🎉 Completato in {round(end_time - start_time, 2)} secondi. File dati_sensori.json pronto.")

if __name__ == "__main__":
    main()
