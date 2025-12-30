import feedparser
import json
import re
import datetime

def analizza_testo(testo):
    testo = testo.lower()
    info = {
        "tendenza": "stazionaria",
        "problema_principale": "non specificato",
        "quota_neve": "non indicata"
    }
    
    # Estrazione Tendenza
    if "in aumento" in testo: info["tendenza"] = "in aumento"
    elif "in diminuzione" in testo: info["tendenza"] = "in diminuzione"
    
    # Estrazione Problema Valanghivo Tipico
    if "neve fresca" in testo: info["problema_principale"] = "neve fresca"
    elif "lastroni" in testo: info["problema_principale"] = "lastroni da vento"
    elif "neve bagnata" in testo: info["problema_principale"] = "neve bagnata"
    
    # Estrazione Quota (es: "oltre i 1200 metri")
    quota_match = re.search(r"oltre i (\d+)\s*m", testo)
    if quota_match:
        info["quota_neve"] = f"{quota_match.group(1)}m"
        
    return info

def scrape():
    url = "https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13"
    feed = feedparser.parse(url)
    
    if not feed.entries: return

    item = feed.entries[0]
    descrizione = item.summary.replace('\n', ' ').strip()
    
    # Analisi avanzata
    analisi = analizza_testo(descrizione)
    match_pericolo = re.search(r"pericolo (\d)", descrizione.lower())
    grado = int(match_pericolo.group(1)) if match_pericolo else 0

    valanghe_data = {
        "settore": "Appennino Lucano",
        "ultimo_aggiornamento": item.published,
        "grado_pericolo": grado,
        "tendenza": analisi["tendenza"],
        "problema_principale": analisi["problema_principale"],
        "quota_critica": analisi["quota_neve"],
        "sintesi": descrizione,
        "link_ufficiale": item.link
    }

    with open('valanghe.json', 'w', encoding='utf-8') as f:
        json.dump(valanghe_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    scrape()
