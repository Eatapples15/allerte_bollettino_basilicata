import requests
import json
import datetime
import os
import feedparser
import re

def invia_telegram_pdf(pdf_url, data_display):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = "-1003527149783"
    if not token: 
        print("Errore: TELEGRAM_TOKEN non configurato")
        return

    # Nome file richiesto: BOLLETTINO_VALANGHE_GG-MM-AAAA.pdf
    nome_file = f"BOLLETTINO_VALANGHE_{data_display.replace('/', '-')}.pdf"
    
    try:
        response = requests.get(pdf_url, timeout=20)
        if response.status_code == 200:
            url_doc = f"https://api.telegram.org/bot{token}/sendDocument"
            files = {'document': (nome_file, response.content)}
            data = {'chat_id': chat_id, 'caption': f"🏔 Bollettino Valanghe del {data_display}"}
            requests.post(url_doc, data=data, files=files)
            print(f"PDF inviato con successo: {nome_file}")
        else:
            print(f"PDF non ancora disponibile sul server Meteomont (Status: {response.status_code})")
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    oggi = datetime.datetime.now()
    data_api = oggi.strftime("%Y-%m-%d")
    data_display = oggi.strftime("%d/%m/%Y")

    try:
        # --- 1. SCOPERTA DATI DA API (Nessun dato fisso) ---
        # Grado Pericolo e Info Settore
        res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers, timeout=15).json()
        p_data = next((p for p in res_p if p.get('idSottoSettore') == 2), {})

        # Stazioni Meteo (Provincia di Potenza)
        res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers, timeout=15).json()
        stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ'] if res_s else []

        # --- 2. SCOPERTA METADATI DA RSS (Per il numero bollettino) ---
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        nr_boll = "N.D."
        if feed.entries:
            entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
            match = re.search(r"Bollettino Valanghe N\.\s*(\d+/\d+)", entry.summary)
            if match: nr_boll = match.group(1)

        # --- 3. COSTRUZIONE URL PDF (Predittivo) ---
        pdf_url = f"https://servizimeteomont.csifa.carabinieri.it/api/meteomontweb/bollettino/getbollettinocl/I/13/2/cl/{data_api}"

        # --- 4. CREAZIONE JSON PER HTML ---
        dati_json = {
            "testata": {
                "settore": "Appennino Lucano",
                "data": data_display,
                "numero": nr_boll,
                "aggiornamento": oggi.strftime("%H:%M")
            },
            "pericolo": {
                "grado": p_data.get("gradoPericolo", "?"),
                "descrizione": p_data.get("descrizioneGradoPericolo", "N.D.").upper(),
                "problema": p_data.get("problemaValanghivo", "Consultare il PDF"),
                "quota": p_data.get("quota", "Vedi PDF")
            },
            "stazioni": [
                {
                    "nome": s.get("nomeStazione", "N/D"),
                    "quota": f"{s.get('quota', 0)}m",
                    "neve": f"{s.get('altezzaNeveAlSuolo', 0)} cm",
                    "temp": f"{s.get('temperaturaMin', '--')}° / {s.get('temperaturaMax', '--')}°"
                } for s in stazioni_lucane
            ],
            "pdf_link": pdf_url
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(dati_json, f, indent=4, ensure_ascii=False)

        # --- 5. INVIO TELEGRAM (Solo il PDF richiesto) ---
        invia_telegram_pdf(pdf_url, data_display)

    except Exception as e:
        print(f"Errore generale: {e}")

if __name__ == "__main__":
    scrape()
