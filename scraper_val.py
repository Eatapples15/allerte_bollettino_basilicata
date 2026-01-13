import requests
import feedparser
import json
import datetime
import os
import re

def invia_telegram(dati, pdf_url):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = "-1003527149783" 
    if not token: return

    # Testo formattato come richiesto
    testo = (
        f"🏔 *BOLLETTINO VALANGHE N. {dati['testata']['nr_bollettino']}*\n"
        f"📅 del {dati['testata']['data_emissione']}\n\n"
        f"⚠️ Pericolo: *{dati['bollettino']['grado_pericolo']} - {dati['bollettino']['label']}*\n"
        f"❄️ *SITUAZIONE:* {dati['bollettino']['situazione_tipo']}\n"
        f"📏 *NEVE MAX:* {dati['meteo_generale']['neve_suolo_max']}\n"
        f"🌡 *ZERO TERMICO:* {dati['meteo_quota']['zero_termico']}\n\n"
        f"📢 *AVVERTENZA:* {dati['bollettino']['avvertenze']}\n\n"
        f"🔗 [Apri PDF Ufficiale]({pdf_url})"
    )

    url_doc = f"https://api.telegram.org/bot{token}/sendDocument"
    requests.post(url_doc, data={'chat_id': chat_id, 'caption': testo, 'parse_mode': 'Markdown'}, 
                  files={'document': ('Bollettino_Valanghe.pdf', requests.get(pdf_url).content)})

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # 1. Recupero Feed RSS (Sempre aggiornato)
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
        testo = entry.summary

        # 2. Estrazione Dinamica dei dati tramite Regex
        # Cerca "Bollettino Valanghe N. XXX/2026 del GG/MM/AAAA"
        info_testata = re.search(r"Bollettino Valanghe N\.\s*(\d+/\d+)\s*del\s*(\d{2}/\d{2}/\d{4})", testo)
        nr_boll = info_testata.group(1) if info_testata else "---/2026"
        data_boll = info_testata.group(2) if info_testata else datetime.datetime.now().strftime("%d/%m/%Y")

        # Cerca il grado di pericolo
        grado_match = re.search(r"PERICOLO:\s*([A-Z]+)\s*(\d)", testo)
        label_p = grado_match.group(1) if grado_match else "DEBOLE"
        grado_p = int(grado_match.group(2)) if grado_match else 1

        # Cerca Zero Termico
        zero_termico = re.search(r"Zero termico\s*([\d-]+ m)", testo)
        quota_zero = zero_termico.group(1) if zero_termico else "N/D"

        # 3. Struttura Dati
        dati = {
            "testata": {
                "settore": "Appennino Lucano",
                "data_emissione": data_boll,
                "nr_bollettino": nr_boll,
                "aggiornamento_script": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            },
            "bollettino": {
                "grado_pericolo": grado_p,
                "label": label_p,
                "situazione_tipo": "In aggiornamento", 
                "manto_nevoso": "Consultare il PDF per i dettagli tecnici del manto.",
                "avvertenze": "Attenzione alle variazioni termiche giornaliere."
            },
            "meteo_generale": {
                "neve_suolo_max": "Vedi stazioni locali",
                "quota_neve_nord": "In aggiornamento",
                "quota_neve_sud": "In aggiornamento"
            },
            "meteo_quota": {
                "zero_termico": quota_zero,
                "quota_1000m": {"temp": "N/D", "vento": "N/D"},
                "quota_2000m": {"temp": "N/D", "vento": "N/D"},
                "quota_3000m": {"temp": "N/D", "percepita": "N/D"}
            },
            "stazioni": [], # Verrà popolato dalle API nei passaggi successivi
            "link_pdf": entry.link
        }

        # Salvataggio e invio
        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(dati, f, indent=4, ensure_ascii=False)
        
        invia_telegram(dati, entry.link)
        print(f"Bollettino {nr_boll} processato.")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
