import requests
import feedparser
import json
import datetime
import os
import re

def invia_telegram(dati, pdf_url):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token: return

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
    except: print("Errore invio Telegram")

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # Recupero Feed RSS per individuare l'ultimo bollettino (Settore 13)
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
        
        # Estrazione Numero e Data tramite Regex
        meta_match = re.search(r"Bollettino Valanghe N\.\s*(\d+/\d+)\s*del\s*(\d{2}/\d{2}/\d{4})", entry.summary)
        nr_boll = meta_match.group(1) if meta_match else "---/2026"
        data_boll = meta_match.group(2) if meta_match else datetime.datetime.now().strftime("%d/%m/%Y")

        # Recupero Dati Pericolo (API strutturata)
        res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers).json()
        p_data = next((p for p in res_p if p.get('idSottoSettore') == 2), res_p[0])

        # Recupero Dati Stazioni Real-Time (Basilicata - PZ)
        res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers).json()
        stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ']

        dati = {
            "testata": {
                "settore": "Appennino Lucano",
                "data_emissione": data_boll,
                "nr_bollettino": nr_boll,
                "aggiornamento_realtime": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            },
            "bollettino": {
                "grado_pericolo": p_data.get("gradoPericolo", 1),
                "label": p_data.get("descrizioneGradoPericolo", "DEBOLE").upper(),
                "situazione_tipo": p_data.get("problemaValanghivo", "Situazione primaverile"),
                "avvertenze": "Evitare le attività fuori pista nelle ore più calde della giornata sui pendii ripidi esposti al sole."
            },
            "meteo_quota": {
                "zero_termico": p_data.get("quota", "2900-3100 m")
            },
            "stazioni": [
                {
                    "nome": s.get("nomeStazione"),
                    "quota": f"{s.get('quota')}m",
                    "neve": f"{s.get('altezzaNeveAlSuolo', 0)} cm",
                    "t_min_max": f"{s.get('temperaturaMin', '--')}° / {s.get('temperaturaMax', '--')}°"
                } for s in stazioni_lucane
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
