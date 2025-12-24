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
    options.add_argument("--blink-settings=imagesEnabled=false")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

drivers = [create_driver() for _ in range(NUM_WORKERS)]

def get_detailed_data(index, sid, sname, category):
    driver = drivers[index % NUM_WORKERS]
    try:
        driver.get(f"https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php?id={sid}")
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        vals = []
        # Estrazione della colonna "Valore"
        for tr in soup.find_all("tr")[1:]:
            tds = r.find_all("td") if (r := tr) else []
            if len(tds) >= 2:
                try:
                    num = float(re.findall(r"[-+]?\d*\.\d+|\d+", tds[1].text.replace(",", "."))[0])
                    vals.append(num)
                except: continue
        
        data_obj = {
            "id": sid, "nome": sname, "valore": vals[0] if vals else 0,
            "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        }

        if category == "pluviometria":
            data_obj["dati_multipli"] = {
                "1h": round(sum(vals[:4]), 1) if len(vals) >= 4 else (vals[0] if vals else 0),
                "3h": round(sum(vals[:12]), 1) if len(vals) >= 12 else 0,
                "6h": round(sum(vals[:24]), 1) if len(vals) >= 24 else 0,
                "12h": round(sum(vals[:48]), 1) if len(vals) >= 48 else 0,
                "24h": round(sum(vals[:96]), 1) if len(vals) >= 96 else 0
            }
        return data_obj
    except: return None

def scrape_category(code, label):
    driver = drivers[0]
    driver.get(f"https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st={code}")
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    stations = []
    for a in soup.find_all("a", href=re.compile(r"id=\d+")):
        name = a.get_text(strip=True)
        sid = re.search(r'id=(\d+)', a['href']).group(1)
        if sid and name and not any(u in name.lower() for u in ["mm", " m", "°c", "hpa"]):
            stations.append((sid, name))
    return list(set(stations))

def main():
    start = time.time()
    categories = {"pluviometria": "P", "idrometria": "I", "termometria": "T", "anemometria": "VV"}
    final_output = {"ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "sensori": {}}

    for cat_name, code in categories.items():
        print(f"Scraping {cat_name}...")
        base_list = scrape_category(code, cat_name)
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as ex:
            results = [r for r in ex.map(lambda p: get_detailed_data(p[0], p[1][0], p[1][1], cat_name), enumerate(base_list)) if r]
        final_output["sensori"][cat_name] = {"dati": results}

    with open("dati_sensori.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)
    
    for d in drivers: d.quit()
    print(f"✅ Completato in {int(time.time()-start)}s")

if __name__ == "__main__": main()
