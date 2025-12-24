import json, datetime, re, time
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

NUM_WORKERS = 4 # Bilanciamento tra velocità e stabilità

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--blink-settings=imagesEnabled=false")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

drivers = [create_driver() for _ in range(NUM_WORKERS)]

def get_detailed_history(index, sid, sname, cat_key):
    driver = drivers[index % NUM_WORKERS]
    url = f"https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php?id={sid}"
    try:
        driver.get(url)
        # Attesa forzata del caricamento della tabella dati
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        time.sleep(1) 
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")
        vals = []
        
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) >= 2:
                # Pulizia del testo per estrarre solo il numero
                raw_val = tds[1].get_text(strip=True).replace(",", ".")
                match = re.findall(r"[-+]?\d*\.\d+|\d+", raw_val)
                if match:
                    vals.append(float(match[0]))

        data_obj = {
            "id": sid,
            "nome": sname,
            "valore": vals[0] if vals else 0.0,
            "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "status": "normal"
        }

        # Calcolo cumulati solo per Pluviometria
        if cat_key == "pluviometria":
            data_obj["dati_multipli"] = {
                "1h": round(sum(vals[:4]), 1) if len(vals) >= 4 else (vals[0] if vals else 0.0),
                "3h": round(sum(vals[:12]), 1) if len(vals) >= 12 else 0.0,
                "6h": round(sum(vals[:24]), 1) if len(vals) >= 24 else 0.0,
                "12h": round(sum(vals[:48]), 1) if len(vals) >= 48 else 0.0,
                "24h": round(sum(vals[:96]), 1) if len(vals) >= 96 else 0.0
            }
        return data_obj
    except Exception as e:
        print(f"⚠️ Errore stazione {sid} ({sname}): {e}")
        return None

def scrape_main_list(code):
    driver = drivers[0]
    driver.get(f"https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st={code}")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "linkStazione")))
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    stations = []
    links = soup.find_all("a", class_="linkStazione")
    
    for a in links:
        name = a.get_text(strip=True)
        href = a.get('href', '')
        sid_match = re.search(r'id=(\d+)', href)
        if sid_match:
            sid = sid_match.group(1)
            # Evita di scambiare il valore per il nome
            if name and not any(u in name.lower() for u in ["mm", " m", "°c", "hpa"]):
                stations.append((sid, name))
    
    return list(dict.fromkeys(stations)) # Rimuove duplicati mantenendo l'ordine

def main():
    start = time.time()
    # Definizione completa dei sensori obbligatori
    SENSORI_CONFIG = {
        "pluviometria": "P",
        "idrometria": "I",
        "anemometria": "VV",
        "termometria": "T",
        "nivometria": "N"
    }
    
    final_output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    for key, code in SENSORI_CONFIG.items():
        print(f"🔍 Scansione categoria: {key}...")
        base_list = scrape_main_list(code)
        
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            # Avviamo il recupero dei dettagli per ogni stazione trovata
            results = [r for r in executor.map(lambda p: get_detailed_history(p[0], p[1][0], p[1][1], key), enumerate(base_list)) if r]
        
        final_output["sensori"][key] = {"dati": results}
        print(f"✅ {key.capitalize()}: {len(results)} stazioni acquisite.")

    # Salvataggio JSON definitivo
    with open("dati_sensori.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)
    
    for d in drivers: d.quit()
    print(f"🎉 Scraping terminato in {int(time.time()-start)}s. File pronto per cfd.html")

if __name__ == "__main__":
    main()
