import requests
import feedparser
import json
import datetime
import re

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # URL definitivi
    url_rss = "https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13"
    url_stazioni_all = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13"
    url_pericolo = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13"

    try:
        # 1. Recupero RSS e filtraggio per BASILICATA
        feed = feedparser.parse(url_rss)
        sintesi = "Bollettino non disponibile"
        link_pdf = "#"
        data_boll = "N/D"
        
        for entry in feed.entries:
            if "lucano" in entry.summary.lower() or "basilicata" in entry.summary.lower():
                sintesi = entry.summary.replace('\n', ' ').strip()
                link_pdf = entry.link
                data_boll = entry.published
                break
        
        # 2. Recupero Dati Stazioni - Cerchiamo la 17, altrimenti la prima lucana attiva
        res_stazioni = requests.get(url_stazioni_all, headers=headers)
        stazioni_list = res_stazioni.json()
        
        # Cerchiamo Monte Pierfaone (17) o Sellata (16) o simili
        stazione_target = next((s for s in stazioni_list if s.get('idStazione') == 17), None)
        if not stazione_target or stazione_target.get('temperaturaAria') == None:
            stazione_target = next((s for s in stazioni_list if s.get('provincia') == 'PZ'), stazioni_list[0])

        # 3. Recupero Pericolo
        res_pericolo = requests.get(url_pericolo, headers=headers)
        pericolo_list = res_pericolo.json()
        pericolo_data = next((p for p in pericolo_list if "lucano" in p.get('sottoSettore', '').lower()), pericolo_list[0])

        data_finale = {
            "testata": {
                "regione": "Basilicata",
                "stazione_monitorata": stazione_target.get("nomeStazione", "Appennino Lucano"),
                "data_bollettino": data_boll,
                "ultima_lettura_api": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            },
            "pericolo": {
                "grado": pericolo_data.get("gradoPericolo", 0),
                "tendenza": pericolo_data.get("tendenza", "stazionaria"),
                "problema": pericolo_data.get("problemaValanghivo", "non specificato"),
                "quota": pericolo_data.get("quota", "n/d")
            },
            "meteo_reale": {
                "neve_al_suolo": stazione_target.get("altezzaNeveAlSuolo", 0) or 0,
                "neve_fresca_24h": stazione_target.get("altezzaNeveFresca24h", 0) or 0,
                "temperatura": stazione_target.get("temperaturaAria", "n/d"),
                "vento": f"{stazione_target.get('velocitaVento', 0)} km/h {stazione_target.get('direzioneVento', '')}"
            },
            "dettagli": {
                "sintesi": sintesi,
                "link_pdf": link_pdf
            }
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(data_finale, f, indent=4, ensure_ascii=False)
        
        print("Scraping ottimizzato completato.")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
