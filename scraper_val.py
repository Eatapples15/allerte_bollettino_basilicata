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
        f"📢 *RIASSUNTO:* {dati['bollettino']['manto_nevoso'][:150]}...\n\n"
        f"🔗 [Apri PDF Ufficiale]({pdf_url})"
    )

    url_doc = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        pdf_res = requests.get(pdf_url, timeout=15)
        if pdf_res.status_code == 200:
            requests.post(url_doc, data={'chat_id': chat_id, 'caption': testo, 'parse_mode': 'Markdown'}, 
                          files={'document': ('Bollettino_Valanghe.pdf', pdf_res.content)})
    except: pass

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # 1. SCOPERTA BOLLETTINO tramite RSS
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        
        # Controllo sicurezza: se il feed è vuoto, lo script non crasha
        if not feed.entries:
            print("Feed RSS momentaneamente non disponibile.")
            return

        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
        testo_boll = entry.summary
        
        # Estrazione dinamica N. e Data (es. Bollettino N. 211/2026 del 13/01/2026)
        meta = re.search(r"Bollettino Valanghe N\.\s*(\d+/\d+)\s*del\s*(\d{2}/\d{2}/\d{4})", testo_boll)
        nr_boll = meta.group(1) if meta else "N/D"
        data_boll = meta.group(2) if meta else datetime.datetime.now().strftime("%d/%m/%Y")

        # 2. API GRADO PERICOLO
        res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers, timeout=10).json()
        p_data = next((p for p in res_p if p.get('idSottoSettore') == 2), res_p[0] if res_p else {})

        # 3. API STAZIONI (Rilevamenti in Basilicata/PZ)
        res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers, timeout=10).json()
        stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ'] if res_s else []

        # 4. INTEGRAZIONE TESTUALE (Regex per scoprire dettagli nel sommario)
        situazione = re.search(r"SITUAZIONE TIPO:\s*([^.]+)", testo_boll)
        manto = re.search(r"MANTO NEVOSO:\s*([^.]+)", testo_boll)
        
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
                "situazione_tipo": situazione.group(1).strip() if situazione else "Situazione primaverile",
                "manto_nevoso": manto.group(1).strip() if manto else "Stabilità buona su alcuni punti.",
                "avvertenze": "Evitare attività fuori pista nelle ore più calde su pendii ripidi al sole."
            },
            "meteo_quota": {
                "zero_termico": p_data.get("quota", "2900-3100 m")
            },
            "stazioni": [
                {
                    "nome": s.get("nomeStazione", "N/D"),
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
        print(f"Scraping completato per Bollettino {nr_boll}")

    except Exception as e:
        print(f"Errore durante lo scraping: {e}")

if __name__ == "__main__":
    scrape()
