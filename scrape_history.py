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

NUM_WORKERS = 4 

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--blink-settings=imagesEnabled=false")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

drivers = [create_driver() for _ in range(NUM_WORKERS)]

def get_history(index, sid, sname):
    driver = drivers[index % NUM_WORKERS]
    url = f"https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php?id={sid}"
    try:
        driver.get(url)
        
        # ATTESA: Aspetta che la tabella dei dati storici sia visibile
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tr td"))
        )
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # Troviamo la tabella corretta (spesso è l'unica con molte righe)
        rows = soup.find_all("tr")
        vals = []
        
        for tr in rows:
            tds = tr.find_all("td")
            # Cerchiamo la riga che ha la data nella prima colonna e il valore nella seconda
            if len(tds) >= 2:
                raw_text = tds[1].get_text(strip=True).replace(",", ".")
                # Estraiamo solo il numero (gestisce casi come "0.2 mm" o stringhe sporche)
                match = re.search(r"[-+]?\d*\.\d+|\d+", raw_text)
                if match:
                    vals.append(float(match.group()))

        if not vals:
            print(f"⚠️ Nessun dato trovato per {sname} ({sid})")
            return None

        # Calcolo somme mobili (assumendo dati ogni 15 minuti)
        return {
            "nome": sname,
            "id": sid,
            "dati_multipli": {
                "1h": round(sum(vals[:4]), 1) if len(vals) >= 4 else round(sum(vals), 1),
                "3h": round(sum(vals[:12]), 1) if len(vals) >= 12 else round(sum(vals), 1),
                "6h": round(sum(vals[:24]), 1) if len(vals) >= 24 else round(sum(vals), 1),
                "12h": round(sum(vals[:48]), 1) if len(vals) >= 48 else round(sum(vals), 1),
                "24h": round(sum(vals[:96]), 1) if len(vals) >= 96 else round(sum(vals), 1)
            }
        }
    except Exception as e:
        print(f"❌ Errore su {sname}: {e}")
        return None

def main():
    print("⏳ Avvio scraping storico stazioni (Pluviometria)...")
    try:
        drivers[0].get("https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st=P")
        WebDriverWait(drivers[0], 15).until(EC.presence_of_element_located((By.CLASS_NAME, "linkStazione")))
        
        soup = BeautifulSoup(drivers[0].page_source, 'html.parser')
        links = soup.find_all("a", href=re.compile(r"id=\d+"))
        
        stations = []
        for a in links:
            name = a.get_text(strip=True)
            sid = re.search(r'id=(\d+)', a['href']).group(1)
            # Filtro per evitare di prendere i valori come nomi
            if sid and name and not any(u in name.lower() for u in ["mm", " m", "°c"]):
                stations.append((sid, name))
        
        stations = list(set(stations))
        print(f"📊 Analisi storica di {len(stations)} stazioni in corso...")

        results = []
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
            # Usiamo un wrapper per passare l'indice
            futures = [ex.submit(get_history, i, s[0], s[1]) for i, s in enumerate(stations)]
            for future in futures:
                res = future.result()
                if res:
                    results.append(res)

        output = {
            "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "stazioni_storico": results
        }

        with open("dati_storici.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        
        print(f"✅ Scraping completato. Elaborate {len(results)} stazioni.")
        
    finally:
        for d in drivers:
            d.quit()

if __name__ == "__main__":
    main()
