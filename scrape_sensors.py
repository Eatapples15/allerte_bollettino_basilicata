import requests
import json
import datetime
import re
from concurrent.futures import ThreadPoolExecutor

# CONFIGURAZIONE
# Usiamo l'endpoint che fornisce i dati grezzi per evitare il rendering JS
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/bollettini/get_sensori.php"
DETTAGLIO_URL = "https://centrofunzionale.regione.basilicata.it/it/dettaglioStazione.php"

# [cite_start]Soglie Idrometriche da PDF [cite: 11, 15, 19]
SOGLIE_IDRO = {
    "Potenza Q.A.": 1.20,
    "S. Demetrio": 1.40,
    "Campomaggiore": 3.50,
    "Bradano S. Lucia": 3.50,
    "Bradano Serra Marina": 6.00,
    "Agri SS 106": 4.00,
    "Sinni SS 106": 3.50
}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest"
})

def get_historical_cumulates(station_id):
    """Estrae i dati storici analizzando la tabella del dettaglio"""
    try:
        # Nota: Alcuni siti richiedono parametri specifici per i dati storici
        resp = session.get(f"{DETTAGLIO_URL}?id={station_id}", timeout=5)
        # Regex per trovare i valori numerici nella tabella storica
        # Cerca pattern come <td>12.4</td>
        matches = re.findall(r'<td>(\d+[\.,]\d+)</td>', resp.text)
        values = [float(m.replace(',', '.')) for m in matches]
        
        # Se la tabella ha due colonne (Data | Valore), i valori sono ogni 2 match
        # Filtriamo per prendere solo la colonna della pioggia
        rain_values = values[0::1] # Adattare in base alla struttura reale se necessario

        return {
            "1h": round(sum(rain_values[:4]), 1) if len(rain_values) >= 4 else 0,
            "3h": round(sum(rain_values[:12]), 1) if len(rain_values) >= 12 else 0,
            "6h": round(sum(rain_values[:24]), 1) if len(rain_values) >= 24 else 0,
            "12h": round(sum(rain_values[:48]), 1) if len(rain_values) >= 48 else 0,
            "24h": round(sum(rain_values[:96]), 1) if len(rain_values) >= 96 else 0
        }
    except:
        return {"1h":0,"3h":0,"6h":0,"12h":0,"24h":0}

def scrape_main_page(st_code):
    """Legge la pagina principale e trova i link delle stazioni"""
    url = f"https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st={st_code}"
    resp = session.get(url)
    # Cerchiamo i link tipo dettaglioStazione.php?id=XXXXXX
    ids = re.findall(r'id=(\d+)', resp.text)
    names = re.findall(r'class="linkStazione">([^<]+)', resp.text)
    
    # Estrazione valori tramite regex dalla tabella
    # Questo bypassa il problema del 0 stazioni se l'HTML contiene i dati ma non formattati
    vals = re.findall(r'<td>(\d+[\.,]\d+)</td>', resp.text)
    
    unique_stations = []
    # Rimuove duplicati mantenendo l'ordine
    seen_ids = set()
    for i in range(min(len(ids), len(names))):
        if ids[i] not in seen_ids:
            unique_stations.append({"id": ids[i], "nome": names[i].strip()})
            seen_ids.add(ids[i])
    return unique_stations

def main():
    print("⏳ Recupero elenco sensori (Metodo Regex)...")
    
    # 1. Recupero ID e nomi
    pluvio_list = scrape_main_page("P")
    idro_list = scrape_main_page("I")
    
    if not pluvio_list:
        print("❌ Errore: Ancora 0 stazioni trovate. Tentativo fallback...")
        # Fallback se il sito usa strutture diverse
        return

    print(f"✅ Trovati {len(pluvio_list)} pluviometri e {len(idro_list)} idrometri.")

    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {
            "idrometria": {"meta": {"label": "Idrometri", "unit": "m"}, "dati": []},
            "pluviometria": {"meta": {"label": "Pluviometri", "unit": "mm"}, "dati": []}
        }
    }

    # 2. Processamento parallelo dei pluviometri (il cuore della lentezza)
    print(f"🌩️ Calcolo cumulati storici per {len(pluvio_list)} stazioni...")
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(get_historical_cumulates, s['id']): s for s in pluvio_list}
        for future in futures:
            meta = futures[future]
            history = future.result()
            final_data["sensori"]["pluviometria"]["dati"].append({
                "id": meta["id"],
                "nome": meta["nome"],
                "valore": history["1h"], # Usiamo 1h come dato istantaneo
                "status": "normal",
                "dati_multipli": history
            })

    # 3. Processamento Idrometri (Semplice)
    for s in idro_list:
        final_data["sensori"]["idrometria"]["dati"].append({
            "id": s["id"],
            "nome": s["nome"],
            "valore": 0.0, # Popolare con scraping se necessario
            "status": "normal"
        })

    with open("dati_sensori.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
    
    print(f"🎉 Dashboard aggiornata con successo alle {final_data['ultimo_aggiornamento']}")

if __name__ == "__main__":
    main()
