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

NUM_WORKERS = 3 # Ridotto leggermente per maggiore stabilità su GitHub

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

drivers = [create_driver() for _ in range(NUM_WORKERS)]

def get_history(index, sid, sname):
    driver = drivers[index % NUM_WORKERS]
    url = f"https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php?id={sid}"
    try:
        driver.get(url)
        # Aspetta che esista almeno una tabella
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")
        vals = []
        
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) >= 2:
                # Estrazione pulita del valore numerico
                raw_text = tds[1].get_text(strip=True).replace(",", ".")
                match = re.search(r"[-+]?\d*\.\d+|\d+", raw_text)
                if match:
                    vals.append(float(match.group()))

        if not vals: return None

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
    except:
        return None

def main():
    print("⏳ Avvio scraping storico stazioni...")
    try:
        driver = drivers[0]
        driver.get("https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st=P")
        
        # Fallback manuale se l'attesa fallisce
        try:
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='id=']")))
        except:
            print("⚠️ Timeout attesa elementi, provo lettura diretta sorgente...")

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        links = soup.find_all("a", href=re.compile(r"id=\d+"))
        
        stations = []
        for a in links:
            name = a.get_text(strip=True)
            sid_match = re.search(r'id=(\d+)', a['href'])
            if sid_match:
                sid = sid_match.group(1)
                # Filtra valori mm che a volte finiscono nel tag nome
                if sid and name and not any(u in name.lower() for u in ["mm", " m", "°c"]):
                    stations.append((sid, name))
        
        stations = list(dict.fromkeys(stations)) # Rimuove duplicati
        print(f"📊 Analisi storica di {len(stations)} stazioni in corso...")

        results = []
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
            futures = [ex.submit(get_history, i, s[0], s[1]) for i, s in enumerate(stations)]
            for future in futures:
                res = future.result()
                if res: results.append(res)

        output = {
            "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "stazioni_storico": results
        }

        with open("dati_storici.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        
        print(f"✅ Completato. {len(results)} stazioni storiche salvate.")
        
    finally:
        for d in drivers: d.quit()

if __name__ == "__main__":
    main()
