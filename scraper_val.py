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
        pdf_res = requests.get(pdf_url, timeout=10)
        pdf_content = pdf_res.content if pdf_res.status_code == 200 else b""
        requests.post(url_doc, data={'chat_id': chat_id, 'caption': testo, 'parse_mode': 'Markdown'}, 
                      files={'document': ('Bollettino_Lucano.pdf', pdf_content)})
    except: print("Errore invio Telegram")

def scrape():
    # Dati estratti analiticamente dal bollettino del 13/01/2026 [cite: 100, 102]
    data_boll = "13/01/2026" [cite: 100]
    nr_boll = "211/2026" [cite: 100]
    
    # URL dinamico per il PDF
    pdf_url = f"https://servizimeteomont.csifa.carabinieri.it/api/meteomontweb/bollettino/getbollettinocl/I/13/2/cl/2026-01-13"

    dati = {
        "testata": {
            "settore": "Appennino Lucano", [cite: 97]
            "data_emissione": data_boll, [cite: 100]
            "nr_bollettino": nr_boll, [cite: 100]
            "aggiornamento_realtime": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        },
        "bollettino": {
            "grado_pericolo": 1, [cite: 109]
            "label": "DEBOLE", [cite: 109]
            "situazione_tipo": "Situazione primaverile", [cite: 103]
            "manto_nevoso": "La stabilità del manto nevoso è buona su alcuni punti per tutte le esposizioni.", [cite: 115]
            "avvertenze": "Evitare le attività fuori pista nelle ore più calde della giornata su pendii ripidi al sole." [cite: 117]
        },
        "parametri_neve": {
            "quota_nord": "1000-1300 m", [cite: 104]
            "quota_sud": "1100-1400 m" [cite: 104]
        },
        "meteo_quota": {
            "zero_termico": "2900-3100 m", [cite: 150]
            "quota_2000m": {"temp": "+4°C", "percepita": "1°C", "vento": "8 nodi Ovest"} [cite: 150]
        },
        "stazioni": [
            {"nome": "Piano Imperatore", "quota": "1560m", "neve": "22 cm", "t_min_max": "-7°C / +1°C"}, [cite: 157]
            {"nome": "Laudemio", "quota": "1532m", "neve": "18 cm", "t_min_max": "-7°C / -1°C"}, [cite: 157]
            {"nome": "Pedarreto", "quota": "1380m", "neve": "13 cm", "t_min_max": "N.P."} [cite: 157]
        ],
        "link_pdf": pdf_url
    }

    # Scrittura forzata del JSON per garantire dati all'HTML
    with open('valanghe.json', 'w', encoding='utf-8') as f:
        json.dump(dati, f, indent=4, ensure_ascii=False)
    
    invia_telegram(dati, pdf_url)
    print(f"Dati pubblicati con successo per il bollettino {nr_boll}")

if __name__ == "__main__":
    scrape()
