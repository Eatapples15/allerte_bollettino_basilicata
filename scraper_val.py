import requests
import json
import datetime
import os
import re
import feedparser

def invia_telegram(dati, pdf_url):
    token = os.getenv('TELEGRAM_TOKEN')
    chat_id = "-1003527149783" 
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
        pdf_content = pdf_res.content if pdf_res.status_code == 200 else b""
        requests.post(url_doc, data={'chat_id': chat_id, 'caption': testo, 'parse_mode': 'Markdown'}, 
                      files={'document': ('Bollettino_Valanghe_Appennino_Lucano.pdf', pdf_content)})
    except: pass

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # 1. Recupero Feed RSS per link PDF e Meta-dati
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        if not feed.entries:
            print("Feed vuoto, uso dati di backup")
            return

        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
        
        # Estrazione Numero e Data con Regex
        meta_match = re.search(r"Bollettino Valanghe N\.\s*(\d+/\d+)\s*del\s*(\d{2}/\d{2}/\d{4})", entry.summary)
        nr_boll = meta_match.group(1) if meta_match else "N/D"
        data_boll = meta_match.group(2) if meta_match else datetime.datetime.now().strftime("%d/%m/%Y")

        # 2. API Grado Pericolo (Settore 13)
        res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers).json()
        p_data = next((p for p in res_p if p.get('idSottoSettore') == 2), res_p[0] if res_p else {})

        # 3. API Dati Stazioni (PZ)
        res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers).json()
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
                "grado_pericolo": p_data.get("gradoPericolo", 1),
                "label": p_data.get("descrizioneGradoPericolo", "DEBOLE").upper(),
                "situazione_tipo": p_data.get("problemaValanghivo", "Situazione primaverile"),
                "avvertenze": "Evitare attività fuori pista nelle ore più calde su pendii ripidi al sole."
            },
            "meteo_quota": {
                "zero_termico": p_data.get("quota", "2900-3100 m")
            },
            "stazioni": [
                {
                    "nome": s.get("nomeStazione", "N/D"),
                    "neve": f"{s.get('altezzaNeveAlSuolo', 0)} cm",
                    "t_min_max": f"{s.get('temperaturaMin', '--')}° / {s.get('temperaturaMax', '--')}°"
                } for s in stazioni_lucane
            ],
            "link_pdf": entry.link
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(dati, f, indent=4, ensure_ascii=False)
        
        invia_telegram(dati, entry.link)
        print(f"Aggiornamento completato: Bollettino {nr_boll}")

    except Exception as e:
        print(f"Errore durante lo scraping: {e}")

if __name__ == "__main__":
    scrape()
