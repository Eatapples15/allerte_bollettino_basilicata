import requests
import feedparser
import json
import datetime
import os
import re

def calcola_wind_chill(t, v_kmh):
    if t <= 10 and v_kmh > 4.8:
        return round(13.12 + 0.6215 * t - 11.37 * (v_kmh**0.16) + 0.3965 * t * (v_kmh**0.16), 1)
    return t

def invia_telegram(dati, pdf_url):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return

    # Testo semplice per il riassunto
    testo_riassunto = (
        f"🏔 *Bollettino Valanghe: Appennino Lucano*\n"
        f"📅 Data: {dati['testata']['data_emissione']}\n"
        f"⚠️ Pericolo: *{dati['bollettino']['grado_pericolo']} - {dati['bollettino']['label']}*\n"
        f"❄️ Situazione: {dati['bollettino']['situazione_tipo']}\n"
        f"🌡 Temp: {dati['meteo']['temp_reale']} (Percepita: {dati['meteo']['temp_percepita']})\n"
        f"📏 Neve: {dati['meteo']['neve_suolo']} a {dati['meteo']['stazione']}\n\n"
        f"📢 *Avvertenza:* {dati['bollettino']['avvertenze']}"
    )

    # Invio del Documento PDF
    url_doc = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {'document': requests.get(pdf_url).content}
    data = {'chat_id': chat_id, 'caption': testo_riassunto, 'parse_mode': 'Markdown'}
    requests.post(url_doc, data=data, files={'document': ('Bollettino_Lucano.pdf', files['document'])})

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # API Meteomont
        res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers).json()
        p_data = next((p for p in res_p if "lucano" in p.get('sottoSettore', '').lower()), res_p[0])
        
        res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers).json()
        stazione = next((s for s in res_s if s.get('idStazione') == 17 or s.get('provincia') == 'PZ'), res_s[0])
        
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])

        t_reale = stazione.get('temperaturaAria', 0)
        v_kmh = stazione.get('velocitaVento', 0)
        
        labels = ["Nessuno", "Debole", "Moderato", "Marcato", "Forte", "Molto Forte"]
        
        dati_json = {
            "testata": {
                "settore": "Appennino Lucano",
                "stazione": stazione.get("nomeStazione", "Monte Pierfaone"),
                "data_emissione": datetime.datetime.now().strftime("%d/%m/%Y")
            },
            "bollettino": {
                "grado_pericolo": p_data.get("gradoPericolo", 1),
                "label": labels[p_data.get("gradoPericolo", 1)],
                "situazione_tipo": "Situazione primaverile",
                "avvertenze": "Evitare attività fuori pista nelle ore più calde su pendii ripidi al sole.",
                "manto_nevoso": "Buona stabilità su alcuni punti per tutte le esposizioni."
            },
            "meteo": {
                "temp_reale": f"{t_reale}°C",
                "temp_percepita": f"{calcola_wind_chill(t_reale, v_kmh)}°C",
                "neve_suolo": f"{stazione.get('altezzaNeveAlSuolo', 0)} cm",
                "vento": f"{v_kmh} km/h"
            },
            "link_pdf": entry.link
        }

        # Aggiorna il file JSON per l'HTML
        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(dati_json, f, indent=4, ensure_ascii=False)
        
        # Invia PDF e riassunto a Telegram
        invia_telegram(dati_json, entry.link)

    except Exception as e: print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
