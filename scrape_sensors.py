import requests
from bs4 import BeautifulSoup
import json
import datetime
import re
from concurrent.futures import ThreadPoolExecutor

# CONFIGURAZIONE URL E SOGLIE
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"
DETTAGLIO_URL = "https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php"
SOGLIE_IDRO = {"Potenza Q.A.": 1.20, "S. Demetrio": 1.40, "Campomaggiore": 3.50, "Bradano Serra Marina": 6.00}

# Sessione per riutilizzare la connessione TCP (velocizza le richieste)
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

def get_historical_data(station_id):
    """Scarica lo storico senza browser in millisecondi"""
    try:
        resp = session.get(f"{DETTAGLIO_URL}?id={station_id}", timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.find_all("tr")[1:]
        values = []
        for r in rows:
            cols = r.find_all("td")
            if len(cols) >= 2:
                try:
                    val = float(cols[1].get_text(strip=True).replace(",", "."))
                    values.append(val)
                except: continue
        
        return {
            "1h": round(sum(values[:4]), 1) if len(values) >= 4 else 0,
            "3h": round(sum(values[:12]), 1) if len(values) >= 12 else 0,
            "6h": round(sum(values[:24]), 1) if len(values) >= 24 else 0,
            "12h": round(sum(values[:48]), 1) if len(values) >= 48 else 0,
            "24h": round(sum(values[:96]), 1) if len(values) >= 96 else 0
        }
    except:
        return {"1h":0,"3h":0,"6h":0,"12h":0,"24h":0}

def scrape_category(code):
    """Ottiene l'elenco stazioni"""
    resp = session.get(f"{BASE_URL}?st={code}", timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    rows = soup.find_all("tr")
    
    stations = []
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
        stations.append({"id": sid, "nome": name, "valore": val_now})
    return stations

def main():
    start_time = datetime.datetime.now()
    print("⏳ Avvio acquisizione ultra-rapida...")

    # Acquisizione Elenchi
    idro_list = scrape_category("I")
    pluvio_list = scrape_category("P")

    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {
            "idrometria": {"meta": {"label": "Idrometri", "unit": "m"}, "dati": []},
            "pluviometria": {"meta": {"label": "Pluviometri", "unit": "mm"}, "dati": []}
        }
    }

    # Processamento Idrometri (Senza storico)
    for s in idro_list:
        status = "alert" if s['nome'] in SOGLIE_IDRO and s['valore'] >= SOGLIE_IDRO[s['nome']] else "normal"
        final_data["sensori"]["idrometria"]["dati"].append({
            **s, "data": final_data["ultimo_aggiornamento"], "status": status
        })

    # Processamento Pluviometri in parallelo (Requests è molto leggero, usiamo 20 thread)
    print(f"🌩️ Elaborazione di {len(pluvio_list)} pluviometri...")
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(get_historical_data, s['id']): s for s in pluvio_list}
        for future in futures:
            s_meta = futures[future]
            history = future.result()
            final_data["sensori"]["pluviometria"]["dati"].append({
                **s_meta, 
                "data": final_data["ultimo_aggiornamento"], 
                "status": "normal", 
                "dati_multipli": history
            })

    with open("dati_sensori.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)

    duration = (datetime.datetime.now() - start_time).total_seconds()
    print(f"✅ Dashboard aggiornata in {duration} secondi.")

if __name__ == "__main__":
    main()
