import json
import datetime
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# CONFIGURAZIONE SOGLIE IDROMETRICHE DA PDF 
SOGLIE_IDRO = {
    "Potenza Q.A.": 1.20,
    "S. Demetrio": 1.40,
    "Campomaggiore": 3.50,
    "Bradano S. Lucia": 3.50,
    "Bradano Serra Marina": 6.00,
    "Agri SS 106": 4.00,
    "Sinni SS 106": 3.50,
    "Ofanto a Monticchio": 2.50
}

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def get_historical_cumulates(driver, station_id):
    """Accede alla tabella storica della stazione e calcola i cumulati."""
    url = f"https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php?id={station_id}"
    try:
        driver.get(url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")[1:]  # Salta intestazione
        
        # Estrae i valori delle ultime 24 ore (intervalli da 15 min = 96 record)
        values = []
        for r in rows:
            cols = r.find_all("td")
            if len(cols) >= 2:
                val = float(cols[1].get_text(strip=True).replace(",", "."))
                values.append(val)
        
        # Calcolo somme mobili basate su 15 min per step 
        return {
            "1h": round(sum(values[:4]), 1) if len(values) >= 4 else 0,
            "3h": round(sum(values[:12]), 1) if len(values) >= 12 else 0,
            "6h": round(sum(values[:24]), 1) if len(values) >= 24 else 0,
            "12h": round(sum(values[:48]), 1) if len(values) >= 48 else 0,
            "24h": round(sum(values[:96]), 1) if len(values) >= 96 else 0
        }
    except Exception as e:
        print(f"⚠️ Errore storico stazione {station_id}: {e}")
        return {"1h":0,"3h":0,"6h":0,"12h":0,"24h":0}

def main():
    driver = setup_driver()
    base_url = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"
    
    final_output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {
            "idrometria": {"meta": {"label": "Idrometri", "unit": "m"}, "dati": []},
            "pluviometria": {"meta": {"label": "Pluviometri", "unit": "mm"}, "dati": []}
        }
    }

    categories = {"idrometria": "I", "pluviometria": "P"}

    for key, code in categories.items():
        print(f"🚀 Scraping categoria: {key}")
        driver.get(f"{base_url}?st={code}")
        time.sleep(4)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue
            
            name = cols[0].get_text(strip=True)
            val_raw = cols[3].get_text(strip=True).replace(",", ".")
            
            try:
                val_now = float(re.findall(r"[-+]?\d*\.\d+|\d+", val_raw)[0])
            except: continue

            # Estrazione ID per navigazione storica
            link = cols[0].find("a")
            sid = re.search(r'id=(\d+)', link['href']).group(1) if link else ""

            entry = {
                "id": sid,
                "nome": name,
                "valore": val_now,
                "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                "status": "normal"
            }

            # Logica specifica PLUVIOMETRI: Cumulati storici 
            if key == "pluviometria":
                print(f"  - Elaborazione storica: {name}")
                entry["dati_multipli"] = get_historical_cumulates(driver, sid)
            
            # Logica specifica IDROMETRI: Confronto soglie PDF 
            if key == "idrometria":
                if name in SOGLIE_IDRO and val_now >= SOGLIE_IDRO[name]:
                    entry["status"] = "alert"

            final_output["sensori"][key]["dati"].append(entry)

    driver.quit()
    
    # Salvataggio JSON per cfd.html
    with open("dati_sensori.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=4, ensure_ascii=False)
    print("✅ Scraping completato e file dati_sensori.json aggiornato.")

if __name__ == "__main__":
    main()
