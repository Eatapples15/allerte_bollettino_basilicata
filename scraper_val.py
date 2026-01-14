import requests
import json
import datetime
import os
import feedparser
import re

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        # 1. RECUPERO FEED RSS (Fonte più affidabile per l'ultimo bollettino esistente)
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        
        if not feed.entries:
            print("Nessun bollettino trovato nel Feed RSS")
            return

        # Cerchiamo l'ultimo per l'Appennino Lucano
        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
        testo_boll = entry.summary
        pdf_url = entry.link

        # ESTRAIAMO LA DATA REALE (es. "del 07/01/2026")
        match_meta = re.search(r"Bollettino Valanghe N\.\s*(\d+/\d+)\s*del\s*(\d{2}/\d{2}/\d{4})", testo_boll)
        nr_boll = match_meta.group(1) if match_meta else "N.D."
        data_reale_boll = match_meta.group(2) if match_meta else "Data non disponibile"
        
        # 2. CHIAMATA API PER DATI LIVE (Sempre aggiornati anche se il PDF è vecchio)
        res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers, timeout=15).json()
        p_data = next((p for p in res_p if p.get('idSottoSettore') == 2), {})
        
        res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers, timeout=15).json()
        stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ']

        # 3. PREPARAZIONE JSON (Tutto dinamico)
        dati_json = {
            "testata": {
                "settore": "Appennino Lucano",
                "data": data_reale_boll, # <--- DATA REALE DEL BOLLETTINO
                "numero": nr_boll,
                "aggiornamento": datetime.datetime.now().strftime("%H:%M")
            },
            "pericolo": {
                "grado": p_data.get("gradoPericolo", "?"),
                "descrizione": p_data.get("descrizioneGradoPericolo", "N.D.").upper(),
                "problema": p_data.get("problemaValanghivo", "Vedi PDF"),
                "quota": p_data.get("quota", "Vedi PDF")
            },
            "stazioni": [
                {
                    "nome": s.get("nomeStazione"),
                    "quota": f"{s.get('quota')}m",
                    "neve": f"{s.get('altezzaNeveAlSuolo', 0)} cm",
                    "temp": f"{s.get('temperaturaMin', '--')}°/{s.get('temperaturaMax', '--')}°"
                } for s in stazioni_lucane
            ],
            "pdf_link": pdf_url
        }

        # Salvataggio file locale
        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(dati_json, f, indent=4, ensure_ascii=False)

        # 4. INVIO TELEGRAM (Solo se configurato)
        token = os.getenv('TELEGRAM_TOKEN')
        chat_id = "-1003527149783"
        if token:
            pdf_res = requests.get(pdf_url)
            data_file = data_reale_boll.replace("/", "-")
            url_doc = f"https://api.telegram.org/bot{token}/sendDocument"
            requests.post(url_doc, 
                data={'chat_id': chat_id, 'caption': f"🏔 Bollettino Valanghe {nr_boll} del {data_reale_boll}"},
                files={'document': (f"BOLLETTINO_VALANGHE_{data_file}.pdf", pdf_res.content)})

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
