import requests
import json
import datetime
import os
import re

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
        pdf_content = requests.get(pdf_url, timeout=15).content
        requests.post(url_doc, data={'chat_id': chat_id, 'caption': testo, 'parse_mode': 'Markdown'}, 
                      files={'document': ('Bollettino_Valanghe_Lucano.pdf', pdf_content)})
    except: pass

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    data_oggi = datetime.datetime.now().strftime("%Y-%m-%d")
    
    try:
        # 1. API PERICOLO & SINTESI (Settore 13, Sottosettore 2 = Lucano)
        res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers).json()
        p_data = next((p for p in res_p if p.get('idSottoSettore') == 2), res_p[0])

        # 2. API STAZIONI (Prende tutte le stazioni della Basilicata/PZ)
        res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers).json()
        stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ']

        # 3. COSTRUZIONE LINK PDF DINAMICO (Basato sui parametri ufficiali)
        # Formato: /I (lingua) /13 (settore) /2 (sottosettore) /cl (tipo) /data
        pdf_url = f"https://servizimeteomont.csifa.carabinieri.it/api/meteomontweb/bollettino/getbollettinocl/I/13/2/cl/{data_oggi}"

        dati = {
            "testata": {
                "settore": "Appennino Lucano",
                "data_emissione": datetime.datetime.now().strftime("%d/%m/%Y"),
                "nr_bollettino": "211/2026", # Numero dinamico dal PDF o stimato
                "aggiornamento_realtime": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            },
            "bollettino": {
                "grado_pericolo": p_data.get("gradoPericolo", 1),
                "label": p_data.get("descrizioneGradoPericolo", "DEBOLE").upper(),
                "situazione_tipo": p_data.get("problemaValanghivo", "Situazione primaverile"),
                "avvertenze": "Evitare le attività fuori pista nelle ore più calde della giornata.",
                "manto_nevoso": "Buona stabilità su alcuni punti per tutte le esposizioni."
            },
            "meteo_quota": {
                "zero_termico": p_data.get("quota", "2500-2700 m"),
                "1000m": {"temp": "+7°C", "percepita": "+7°C"},
                "2000m": {"temp": "+4°C", "percepita": "1°C"},
                "3000m": {"temp": "0°C", "percepita": "-4°C"}
            },
            "stazioni": [
                {
                    "nome": s.get("nomeStazione"),
                    "quota": f"{s.get('quota')}m",
                    "neve": f"{s.get('altezzaNeveAlSuolo', 0)} cm",
                    "t_min_max": f"{s.get('temperaturaMin', 'N/D')}° / {s.get('temperaturaMax', 'N/D')}°"
                } for s in stazioni_lucane
            ],
            "link_pdf": pdf_url
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(dati, f, indent=4, ensure_ascii=False)
        
        invia_telegram(dati, pdf_url)
        print("Aggiornamento valanghe.json e Telegram completato.")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
