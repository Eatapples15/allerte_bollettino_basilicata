import feedparser
import json
import re
import datetime

def scrape():
    # URL del feed RSS specifico per il settore 13 (Basilicata)
    url = "https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13"
    
    print(f"Inizio scraping alle {datetime.datetime.now()}")
    feed = feedparser.parse(url)
    
    if not feed.entries:
        print("Errore: Nessun dato trovato nel feed RSS.")
        return

    # Estrazione dell'ultimo bollettino pubblicato
    item = feed.entries[0]
    
    # Pulizia descrizione e ricerca grado di pericolo (1-5)
    descrizione = item.summary.replace('\n', ' ').strip()
    match_pericolo = re.search(r"pericolo (\d)", descrizione.lower())
    grado_pericolo = int(match_pericolo.group(1)) if match_pericolo else "N/D"
    
    # Creazione della struttura JSON
    valanghe_data = {
        "settore": "Appennino Lucano",
        "regione": "Basilicata",
        "ultimo_aggiornamento": item.published,
        "grado_pericolo": grado_pericolo,
        "titolo": item.title,
        "descrizione_sintetica": descrizione,
        "url_bollettino": item.link,
        "timestamp_esecuzione": str(datetime.datetime.now())
    }

    # Scrittura del file valanghe.json
    with open('valanghe.json', 'w', encoding='utf-8') as f:
        json.dump(valanghe_data, f, indent=4, ensure_ascii=False)
    
    print(f"File valanghe.json aggiornato correttamente. Pericolo: {grado_pericolo}")

if __name__ == "__main__":
    scrape()
