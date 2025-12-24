import json, datetime, re, time
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

NUM_WORKERS = 5

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

drivers = [create_driver() for _ in range(NUM_WORKERS)]

def get_station_history(index, sid, sname):
    driver = drivers[index % NUM_WORKERS]
    try:
        driver.get(f"https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php?id={sid}")
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # Cattura i dati dalla colonna "Valore" della tabella storica
        vals = []
        for tr in soup.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) >= 2:
                try:
                    num = float(re.findall(r"[-+]?\d*\.\d+|\d+", tds[1].text.replace(",", "."))[0])
                    vals.append(num)
                except: continue
        return {
            "id": sid, "nome": sname, "valore": vals[0] if vals else 0,
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
    driver = drivers[0]
    driver.get("https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st=P")
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # FILTRO INFALLIBILE: Solo i link che NON contengono unità di misura nel testo
    raw_links = soup.find_all("a", href=re.compile(r"id=\d+"))
    stations = []
    for a in raw_links:
        name = a.get_text(strip=True)
        sid = re.search(r'id=(\d+)', a['href']).group(1)
        if sid and name and not any(u in name.lower() for u in ["mm", " m", "°c", "hpa"]):
            stations.append((sid, name))
    
    stations = list(set(stations)) # Rimuove duplicati
    print(f"✅ Trovate {len(stations)} stazioni reali. Avvio analisi storica...")

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
        results = [r for r in ex.map(lambda p: get_station_history(p[0], p[1][0], p[1][1]), enumerate(stations)) if r]

    output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": { "pluviometria": {"meta": {"label": "Pluviometri", "unit": "mm"}, "dati": results}, "idrometria": {"dati": []} }
    }
    with open("dati_sensori.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    for d in drivers: d.quit()

if __name__ == "__main__": main()
