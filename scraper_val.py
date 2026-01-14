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
        # 1. RSS: Scoperta link PDF e metadati testuali
        feed = feedparser.parse("https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13")
        if not feed.entries: return
        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
        testo_boll = entry.summary
        
        # Regex per N. e Data (scopre i dati dal testo del giorno)
        meta = re.search(r"Bollettino Valanghe N\.\s*(\d+/\d+)\s*del\s*(\d{2}/\d{2}/\d{4})", testo_boll)
        
        # 2. API GRADO PERICOLO (Dati strutturati)
        res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers, timeout=10).json()
        p_data = next((p for p in res_p if p.get('idSottoSettore') == 2), res_p[0] if res_p else {})

        # 3. API STAZIONI (Rilevamenti reali in provincia di Potenza)
        res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers, timeout=10).json()
        stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ'] if res_s else []

        # 4. PARSING TESTUALE (Estrae i blocchi specifici dal testo del bollettino)
        # Cerchiamo i termini esatti usati nel bollettino (SITUAZIONE TIPO, MANTO, AVVERTENZE)
        sit_tipo = re.search(r"SITUAZIONE TIPO:\s*([^.]+)", testo_boll)
        manto_txt = re.search(r"MANTO NEVOSO:\s*([^.]+)", testo_boll)
        avvertenze_txt = re.search(r"AVVERTENZE:\s*([^.]+)", testo_boll)
        
        dati = {
            "testata": {
                "settore": "Appennino Lucano",
                "data_emissione": meta.group(2) if meta else "Data non disponibile",
                "nr_bollettino": meta.group(1) if meta else "N/D",
                "aggiornamento_realtime": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            },
            "bollettino": {
                "grado_pericolo": p_data.get("gradoPericolo", "N/D"),
                "label": p_data.get("descrizioneGradoPericolo", "N/D").upper(),
                "situazione_tipo": sit_tipo.group(1).strip() if sit_tipo else "Non specificata",
                "manto_nevoso": manto_txt.group(1).strip() if manto_txt else "Vedi PDF",
                "avvertenze": avvertenze_txt.group(1).strip() if avvertenze_txt else "Vedi PDF"
            },
            "meteo_quota": {
                "zero_termico": p_data.get("quota", "Dato non disponibile")
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

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
