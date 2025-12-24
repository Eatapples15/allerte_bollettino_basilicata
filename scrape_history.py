import json, datetime, re, time
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

NUM_WORKERS = 4 # Browser paralleli per velocità

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

drivers = [create_driver() for _ in range(NUM_WORKERS)]

def get_history(index, sid, sname):
    driver = drivers[index % NUM_WORKERS]
    url = f"https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php?id={sid}"
    try:
        driver.get(url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        vals = []
        for tr in soup.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) >= 2:
                try:
                    num = float(re.findall(r"[-+]?\d*\.\d+|\d+", tds[1].text.replace(",", "."))[0])
                    vals.append(num)
                except: continue
        return {
            "nome": sname,
            "id": sid,
            "dati_multipli": {
                "1h": round(sum(vals[:4]), 1) if len(vals) >= 4 else 0,
                "3h": round(sum(vals[:12]), 1) if len(vals) >= 12 else 0,
                "6h": round(sum(vals[:24]), 1) if len(vals) >= 24 else 0,
                "12h": round(sum(vals[:48]), 1) if len(vals) >= 48 else 0,
                "24h": round(sum(vals[:96]), 1) if len(vals) >= 96 else 0
            }
        }
    except: return None

def main():
    print("⏳ Avvio scraping storico stazioni...")
    # Usa il driver 0 per la lista pluviometri
    drivers[0].get("https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st=P")
    time.sleep(5)
    soup = BeautifulSoup(drivers[0].page_source, 'html.parser')
    links = soup.find_all("a", href=re.compile(r"id=\d+"))
    
    stations = []
    for a in links:
        name = a.get_text(strip=True)
        sid = re.search(r'id=(\d+)', a['href']).group(1)
        if sid and name and "mm" not in name.lower():
            stations.append((sid, name))
    
    stations = list(set(stations))
    print(f"📊 Analisi storica di {len(stations)} stazioni...")

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
        results = [r for r in ex.map(lambda p: get_history(p[0], p[1][0], p[1][1]), enumerate(stations)) if r]

    output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "stazioni_storico": results
    }

    with open("dati_storici.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    
    for d in drivers: d.quit()
    print("✅ File dati_storici.json creato.")

if __name__ == "__main__": main()
