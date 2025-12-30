import feedparser
import json
import re
import datetime
import os

def estrai_dati_avanzati(testo):
    testo_low = testo.lower()
    dati = {
        "tendenza": "stazionaria",
        "problema_principale": "non specificato",
        "quota_critica": "n/d",
        "neve_fresca_24h": "0 cm",
        "temperature": {"min": "n/d", "max": "n/d"}
    }
    
    # 1. Tendenza
    if "aumento" in testo_low: dati["tendenza"] = "in aumento 📈"
    elif "diminuzione" in testo_low: dati["tendenza"] = "in diminuzione 📉"
    
    # 2. Problema tipico
    if "neve fresca" in testo_low: dati["problema_principale"] = "Neve fresca"
    elif "lastroni" in testo_low: dati["problema_principale"] = "Lastroni da vento"
    elif "neve bagnata" in testo_low: dati["problema_principale"] = "Neve bagnata"
    elif "ghiaccio" in testo_low: dati["problema_principale"] = "Ghiaccio / Croste"

    # 3. Quota critica (es. oltre i 1500m)
    quota = re.search(r"oltre i (\d+)\s*m", testo_low)
    if quota: dati["quota_critica"] = quota.group(1) + " m"

    # 4. Neve fresca (es. 10-15 cm)
    neve = re.search(r"(\d+)\s*cm di neve fresca", testo_low)
    if neve: dati["neve_fresca_24h"] = neve.group(1) + " cm"

    # 5. Temperature (cerca pattern come -5°C o +2°C)
    temp = re.findall(r"([+-]?\d+)\s*°", testo_low)
    if len(temp) >= 2:
        # Ordiniamo per trovare min e max tra i valori estratti
        valori = sorted([int(t) for t in temp])
        dati["temperature"]["min"] = f"{valori[0]}°C"
        dati["temperature"]["max"] = f"{valori[-1]}°C"
        
    return dati

def scrape():
    url = "https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13"
    feed = feedparser.parse(url)
    
    if not feed.entries:
        print("Errore: Feed non raggiungibile.")
        return

    item = feed.entries[0]
    testo_completo = item.summary.replace('\n', ' ').strip()
    
    # Analisi del testo
    analisi = estrai_dati_avanzati(testo_completo)
    
    # Grado di pericolo
    match_pericolo = re.search(r"pericolo (\d)", testo_completo.lower())
    grado = int(match_pericolo.group(1)) if match_pericolo else 0

    json_finale = {
        "stazione": "Appennino Lucano",
        "data_aggiornamento": item.published,
        "grado_pericolo": grado,
        "info_rapide": analisi,
        "sintesi_testuale": testo_completo,
        "link_pdf": item.link,
        "timestamp_invio": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    }

    with open('valanghe.json', 'w', encoding='utf-8') as f:
        json.dump(json_finale, f, indent=4, ensure_ascii=False)
    
    print("Scraping completato con successo.")

if __name__ == "__main__":
    scrape()
