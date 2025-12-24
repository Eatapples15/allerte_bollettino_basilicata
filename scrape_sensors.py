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

# CONFIGURAZIONE SOGLIE IDROMETRICHE [cite: 11, 15, 19]
SOGLIE_IDRO = {
    "Potenza Q.A.": 1.20,
    "S. Demetrio": 1.40,
    "Campomaggiore": 3.50,
    "Bradano Serra Marina": 6.00,
    "Agri SS 106": 4.00,
    "Sinni SS 106": 3.50
}

def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # Disabilita immagini e estensioni per caricare più velocemente
    options.add_argument("--disable-gpu")
    options.add_argument("--blink-settings=imagesEnabled=false")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def get_station_history(station_id):
    """Funzione atomica per caricare una singola stazione"""
    driver = get_driver()
    url = f"https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php?id={station_id}"
    try:
        driver.get(url)
        time.sleep(1.5) # Tempo minimo per caricamento JS
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")[1:]
        values = []
        for r in rows:
            cols = r.find_all("td")
            if len(cols) >= 2:
                try:
                    val = float(cols[1].get_text(strip=True).replace(",", "."))
                    values.append(val)
                except: continue
        
        # Calcolo somme mobili (assumendo step 15 min) [cite: 1]
        return {
            "1h": round(sum(values[:4]), 1) if len(values) >= 4 else 0,
            "3h": round(sum(values[:12]), 1) if len(values) >= 12 else 0,
            "6h": round(sum(values[:24]), 1) if len(values) >= 24 else 0,
            "12h": round(sum(values[:48]), 1) if len(values) >= 48 else 0,
            "24h": round(sum(values[:96]), 1) if len(values) >= 96 else 0
        }
    except:
        return {"1h":0,"3h":0,"6h":0,"12h":0,"24h":0}
    finally:
        driver.quit()

def process_category(key, code):
    """Estrae l'elenco e poi parallelizza il dettaglio"""
    print(f"🚀 Avvio scraping categoria: {key}")
    driver = get_driver()
    driver.get(f"https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st={code}")
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    rows = soup.find_all("tr")
    
    stations_to_process = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 4: continue
        name = cols[0].get_text(strip=True)
        val_raw = cols[3].get_text(strip=True).replace(",", ".")
        link = cols[0].find("a")
        sid = re.search(r'id=(\d+)', link['href']).group(1) if link else ""
        try:
            val_now = float(re.findall(r"[-+]?\d*\.\d+|\d+", val_raw)[0])
        except: continue
        
        stations_to_process.append({"id": sid, "nome": name, "valore": val_now})
    
    driver.quit()

    # --- PARTE VELOCE: PARALLELIZZAZIONE ---
    final_readings = []
    
    # Usiamo 10 thread simultanei (puoi aumentare se il PC/Server regge)
    with ThreadPoolExecutor(max_workers=10) as executor:
        if key == "pluviometria":
            print(f"  ⚡ Elaborazione parallela di {len(stations_to_process)} pluviometri...")
            # Mappiamo la funzione get_station_history su tutti gli ID
            future_results = {executor.submit(get_station_history, s['id']): s for s in stations_to_process}
            
            for future in future_results:
                station_meta = future_results[future]
                history = future.result()
                final_readings.append({
                    "id": station_meta['id'],
                    "nome": station_meta['nome'],
                    "valore": station_meta['valore'],
                    "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "status": "normal",
                    "dati_multipli": history
                })
        else:
            # Per idrometria non serve entrare nel dettaglio per i cumulati
            for s in stations_to_process:
                status = "alert" if s['nome'] in SOGLIE_IDRO and s['valore'] >= SOGLIE_IDRO[s['nome']] else "normal"
                final_readings.append({
                    "id": s['id'],
                    "nome": s['nome'],
                    "valore": s['valore'],
                    "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "status": status
                })
                
    return final_readings

def main():
    start_time = time.time()
    
    final_output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {
            "idrometria": {"meta": {"label": "Idrometri", "unit": "m"}, "dati": process_category("idrometria", "I")},
            "pluviometria": {"meta": {"label": "Pluviometri", "unit": "mm"}, "dati": process_category("pluviometria", "P")}
        }
    }

    with open("dati_sensori.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)
    
    end_time = time.time()
    print(f"✅ Completato in {round(end_time - start_time, 2)} secondi.")

if __name__ == "__main__":
    main()
