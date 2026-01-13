import requests
import feedparser
import json
import datetime
import os

def invia_telegram(dati, pdf_url):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = "-1003527149783" 
    if not token: return

    testo = (
        f"🏔 *BOLLETTINO VALANGHE: APPENNINO LUCANO*\n"
        f"📅 Data: {dati['testata']['data_emissione']}\n"
        f"⚠️ Pericolo: *{dati['bollettino']['grado_pericolo']} - {dati['bollettino']['label']}*\n\n"
        f"❄️ *SITUAZIONE:* {dati['bollettino']['situazione_tipo']}\n"
        f"📏 *NEVE AL SUOLO:* {dati['meteo_generale']['neve_suolo_max']}\n"
        f"🌡 *ZERO TERMICO:* {dati['meteo_quota']['zero_termico']}\n\n"
        f"📢 *AVVERTENZA:* {dati['bollettino']['avvertenze']}"
    )

    url_doc = f"https://api.telegram.org/bot{token}/sendDocument"
    requests.post(url_doc, data={'chat_id': chat_id, 'caption': testo, 'parse_mode': 'Markdown'}, 
                  files={'document': ('Bollettino_Appennino_Lucano.pdf', requests.get(pdf_url).content)})

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])

        # Struttura completa speculare al PDF del 13/01/2026
        dati = {
            "testata": {
                "settore": "Appennino Lucano",
                "data_emissione": "13/01/2026",
                "nr_bollettino": "211/2026",
                "aggiornamento_script": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            },
            "bollettino": {
                "grado_pericolo": 1,
                "label": "DEBOLE",
                "situazione_tipo": "Situazione primaverile",
                "manto_nevoso": "La stabilità del manto nevoso è buona su alcuni punti per tutte le esposizioni.",
                "avvertenze": "Evitare le attività fuori pista nelle ore più calde della giornata su pendii ripidi al sole."
            },
            "meteo_generale": {
                "neve_suolo_max": "22 cm a 1560m",
                "quota_neve_nord": "1000-1300 m",
                "quota_neve_sud": "1100-1400 m"
            },
            "meteo_quota": {
                "zero_termico": "2900-3100 m",
                "quota_1000m": {"temp": "+7°C", "vento": "2 nodi Ovest"},
                "quota_2000m": {"temp": "+4°C", "vento": "8 nodi Ovest"},
                "quota_3000m": {"temp": "0°C", "percepita": "-4°C"}
            },
            "stazioni": [
                {"localita": "Piano Imperatore", "quota": "1560m", "neve": "22 cm", "t_min_max": "-7°C / +1°C"},
                {"localita": "Laudemio", "quota": "1532m", "neve": "18 cm", "t_min_max": "-7°C / -1°C"},
                {"localita": "Pedarreto", "quota": "1380m", "neve": "13 cm", "t_min_max": "N.P."}
            ],
            "link_pdf": entry.link
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(dati, f, indent=4, ensure_ascii=False)
        
        invia_telegram(dati, entry.link)

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
