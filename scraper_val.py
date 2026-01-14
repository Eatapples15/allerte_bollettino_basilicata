import requests
import feedparser
import json
import datetime
import os
import re

def invia_telegram(dati, pdf_url):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = "-1003527149783" 
    if not token or not chat_id:
        print("Telegram Token o Chat ID non configurati.")
        return

    testo = (
        f"🏔 *BOLLETTINO VALANGHE N. {dati['testata']['nr_bollettino']}*\n"
        f"📅 del {dati['testata']['data_emissione']}\n\n"
        f"⚠️ Pericolo: *{dati['bollettino']['grado_pericolo']} - {dati['bollettino']['label']}*\n"
        f"❄️ *SITUAZIONE:* {dati['bollettino']['situazione_tipo']}\n"
        f"🌡 *ZERO TERMICO:* {dati['meteo_quota']['zero_termico']}\n\n"
        f"📢 *AVVERTENZA:* {dati['bollettino']['avvertenze']}\n\n"
        f"🔗 [Apri PDF Ufficiale]({pdf_url})"
    )

    url_doc = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        pdf_res = requests.get(pdf_url, timeout=15)
        if pdf_res.status_code == 200:
            requests.post(url_doc, data={'chat_id': chat_id, 'caption': testo, 'parse_mode': 'Markdown'}, 
                          files={'document': ('Bollettino_Lucano.pdf', pdf_res.content)})
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # 1. Recupero Feed RSS
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        
        # Controllo se il feed è vuoto per evitare "list index out of range"
        if not feed.entries:
            raise Exception("Il feed RSS di Meteomont è temporaneamente vuoto o non raggiungibile.")

        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
        testo_rss = entry.summary

        # Estrazione Numero e Data tramite Regex
        meta_match = re.search(r"Bollettino Valanghe N\.\s*(\d+/\d+)\s*del\s*(\d{2}/\d{2}/\d{4})", testo_rss)
        nr_boll = meta_match.group(1) if meta_match else "N/D"
        data_boll = meta_match.group(2) if meta_match else datetime.datetime.now().strftime("%d/%m/%Y")

        # 2. API Grado Pericolo (Settore 13)
        res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers, timeout=10).json()
        p_data = next((p for p in res_p if "lucano" in p.get('sottoSettore', '').lower()), res_p[0] if res_p else {})

        # 3. API Dati Stazioni
        res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers, timeout=10).json()
        stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ'] if res_s else []

        # 4. Costruzione JSON
        dati = {
            "testata": {
                "settore": "Appennino Lucano",
                "data_emissione": data_boll,
                "nr_bollettino": nr_boll,
                "aggiornamento_realtime": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            },
            "bollettino": {
                "grado_pericolo": p_data.get("gradoPericolo", 0),
                "label": p_data.get("descrizioneGradoPericolo", "N/D").upper(),
                "situazione_tipo": p_data.get("problemaValanghivo", "In aggiornamento"),
                "avvertenze": "Consultare il PDF per le avvertenze specifiche di oggi.",
            },
            "meteo_quota": {
                "zero_termico": p_data.get("quota", "N/D"),
            },
            "stazioni": [
                {
                    "localita": s.get("nomeStazione", "N/D"),
                    "quota": f"{s.get('quota', 0)}m",
                    "neve": f"{s.get('altezzaNeveAlSuolo', 0)} cm",
                    "t_min_max": f"{s.get('temperaturaMin', '--')}° / {s.get('temperaturaMax', '--')}°"
                } for s in stazioni_lucane
            ],
            "link_pdf": entry.link
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(dati, f, indent=4, ensure_ascii=False)
        
        invia_telegram(dati, entry.link)
        print(f"Scraping riuscito: Bollettino {nr_boll}")

    except Exception as e:
        print(f"Errore durante lo scraping: {e}")

if __name__ == "__main__":
    scrape()
