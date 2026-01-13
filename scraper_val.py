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

    # Testo dinamico basato sul PDF fornito [cite: 464, 473, 475]
    testo = (
        f"🏔 *BOLLETTINO VALANGHE N. {dati['testata']['nr_bollettino']}*\n"
        f"📅 del {dati['testata']['data_emissione']}\n\n"
        f"⚠️ Pericolo: *{dati['bollettino']['grado_pericolo']} - {dati['bollettino']['label']}*\n"
        f"❄️ *SITUAZIONE:* {dati['bollettino']['situazione_tipo']}\n"
        f"📏 *NEVE AL SUOLO:* {dati['meteo_generale']['neve_suolo_max']}\n"
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
        # 1. API PERICOLO (Settore 13) [cite: 473]
        res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers).json()
        p_data = next((p for p in res_p if "lucano" in p.get('sottoSettore', '').lower()), res_p[0])
        
        # 2. API STAZIONI (Settore 13) [cite: 521]
        res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers).json()
        stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ']
        
        # 3. RSS PER NUMERO BOLLETTINO E PDF 
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
        
        # Regex per estrarre Numero e Data dinamicamente 
        meta_match = re.search(r"Bollettino Valanghe N\.\s*(\d+/\d+)\s*del\s*(\d{2}/\d{2}/\d{4})", entry.summary)
        nr_boll = meta_match.group(1) if meta_match else "---/2026"
        data_boll = meta_match.group(2) if meta_match else datetime.datetime.now().strftime("%d/%m/%Y")

        # 4. COSTRUZIONE JSON
        dati = {
            "testata": {
                "settore": "Appennino Lucano",
                "data_emissione": data_boll,
                "nr_bollettino": nr_boll,
                "aggiornamento_script": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            },
            "bollettino": {
                "grado_pericolo": p_data.get("gradoPericolo", 1),
                "label": p_data.get("descrizioneGradoPericolo", "DEBOLE").upper(),
                "situazione_tipo": p_data.get("problemaValanghivo", "Situazione primaverile"),
                "manto_nevoso": "Stabilità del manto nevoso variabile [cite: 479]",
                "avvertenze": "Evitare attività fuori pista nelle ore più calde[cite: 481]."
            },
            "meteo_generale": {
                "neve_suolo_max": f"{max([s.get('altezzaNeveAlSuolo', 0) for s in stazioni_lucane if s.get('altezzaNeveAlSuolo') is not None] or [0])} cm [cite: 521]",
                "quota_neve_nord": "1000-1300 m [cite: 468]",
                "quota_neve_sud": "1100-1400 m [cite: 468]"
            },
            "meteo_quota": {
                "zero_termico": p_data.get("quota", "2900-3100 m [cite: 514]"),
                "quota_2000m": {"temp": "+4°C", "vento": "8 nodi Ovest [cite: 514]"},
                "quota_3000m": {"temp": "0°C", "percepita": "-4°C [cite: 514]"}
            },
            "stazioni": [
                {
                    "localita": s.get("nomeStazione"),
                    "quota": f"{s.get('quota')}m",
                    "neve": f"{s.get('altezzaNeveAlSuolo', 0)} cm",
                    "t_min_max": f"{s.get('temperaturaMin', 'N.P.')}° / {s.get('temperaturaMax', 'N.P.')}°"
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
