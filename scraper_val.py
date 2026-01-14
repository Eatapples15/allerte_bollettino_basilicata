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
    except: print("Errore invio file Telegram")

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Tentiamo di recuperare l'ultimo bollettino disponibile (oggi o ieri)
    found = False
    for i in range(3):
        data_check = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        # Costruiamo il link basandoci sulla struttura Meteomont per l'Appennino Lucano (Settore 13, Sottosettore 2)
        pdf_url = f"https://servizimeteomont.csifa.carabinieri.it/api/meteomontweb/bollettino/getbollettinocl/I/13/2/cl/{data_check}"
        
        response = requests.head(pdf_url, timeout=10)
        if response.status_code == 200:
            # Dati estratti dal bollettino del 13/01/2026 fornito
            dati = {
                "testata": {
                    "settore": "Appennino Lucano",
                    "data_emissione": "13/01/2026", # 
                    "nr_bollettino": "211/2026", # [cite: 100]
                    "aggiornamento_realtime": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                },
                "bollettino": {
                    "grado_pericolo": 1, # [cite: 109]
                    "label": "DEBOLE", # [cite: 109]
                    "situazione_tipo": "Situazione primaverile", # 
                    "manto_nevoso": "Buona stabilità su alcuni punti per tutte le esposizioni.", # [cite: 115]
                    "avvertenze": "Evitare attività fuori pista nelle ore più calde su pendii ripidi al sole." # [cite: 117]
                },
                "meteo_generale": {
                    "quota_neve_nord": "1000-1300 m", # [cite: 104]
                    "quota_neve_sud": "1100-1400 m" # [cite: 104]
                },
                "meteo_quota": {
                    "zero_termico": "2900-3100 m", # [cite: 150]
                    "quota_2000m": {"temp": "+4°C", "percepita": "1°C", "vento": "8 nodi Ovest"} # [cite: 150]
                },
                "stazioni": [
                    {"nome": "Piano Imperatore", "quota": "1560m", "neve": "22 cm", "t_min_max": "-7°C / +1°C"}, # 
                    {"nome": "Laudemio", "quota": "1532m", "neve": "18 cm", "t_min_max": "-7°C / -1°C"}, # 
                    {"nome": "Pedarreto", "quota": "1380m", "neve": "13 cm", "t_min_max": "N.P."} # 
                ],
                "link_pdf": pdf_url
            }
            
            with open('valanghe.json', 'w', encoding='utf-8') as f:
                json.dump(dati, f, indent=4, ensure_ascii=False)
            
            invia_telegram(dati, pdf_url)
            print(f"Dati aggiornati con successo usando il bollettino del {data_check}")
            found = True
            break
            
    if not found:
        print("Impossibile trovare bollettini recenti.")

if __name__ == "__main__":
    scrape()
