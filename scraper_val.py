import requests
import feedparser
import json
import datetime
import re

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. LINK RSS - Per testo descrittivo e link PDF
    url_rss = "https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13"
    # 2. LINK DATI STAZIONE - Per Neve al suolo, Temp e Vento (Monte Pierfaone)
    url_stazione = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/17"
    # 3. LINK GRADO PERICOLO - Per valore numerico e problema tipico
    url_pericolo = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13"

    try:
        # Recupero RSS
        feed = feedparser.parse(url_rss)
        entry = feed.entries[0] if feed.entries else None
        sintesi = entry.summary.replace('\n', ' ').strip() if entry else "Dato non disponibile"

        # Recupero Dati Stazione
        res_stazione = requests.get(url_stazione, headers=headers)
        stazione = res_stazione.json()[0] if res_stazione.json() else {}

        # Recupero Pericolo Strutturato
        res_pericolo = requests.get(url_pericolo, headers=headers)
        pericolo_data = res_pericolo.json()[0] if res_pericolo.json() else {}

        # Merge dei dati in un unico JSON
        data_finale = {
            "testata": {
                "regione": "Basilicata",
                "settore": "Appennino Lucano",
                "stazione": "Monte Pierfaone (PZ)",
                "data_bollettino": entry.published if entry else "N/D",
                "ultima_lettura_api": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            },
            "pericolo": {
                "grado": pericolo_data.get("gradoPericolo", 0),
                "tendenza": pericolo_data.get("tendenza", "stazionaria"),
                "problema": pericolo_data.get("problemaValanghivo", "non specificato"),
                "quota": pericolo_data.get("quota", "n/d")
            },
            "meteo_reale": {
                "neve_al_suolo": stazione.get("altezzaNeveAlSuolo", 0),
                "neve_fresca_24h": stazione.get("altezzaNeveFresca24h", 0),
                "temperatura": stazione.get("temperaturaAria", "n/d"),
                "vento_velocita": stazione.get("velocitaVento", 0),
                "vento_direzione": stazione.get("direzioneVento", "n/d")
            },
            "dettagli": {
                "sintesi": sintesi,
                "link_pdf": entry.link if entry else "#"
            }
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(data_finale, f, indent=4, ensure_ascii=False)
        
        print("Scraping completato con successo: valanghe.json aggiornato.")

    except Exception as e:
        print(f"Errore durante l'ottimizzazione: {e}")

if __name__ == "__main__":
    scrape()
