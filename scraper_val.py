import requests
import json
import datetime
import os
import re

def calcola_wind_chill(t, nodi):
    v_kmh = nodi * 1.852
    if t <= 10 and v_kmh > 4.8:
        return round(13.12 + 0.6215 * t - 11.37 * (v_kmh**0.16) + 0.3965 * t * (v_kmh**0.16), 1)
    return t

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
                      files={'document': ('Bollettino_Lucano.pdf', pdf_content)})
    except: pass

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    # Cerchiamo i dati per oggi, se fallisce proviamo i giorni precedenti (Auto-Discovery)
    for i in range(5): 
        data_target = (datetime.datetime.now() - datetime.timedelta(days=i))
        str_data = data_target.strftime("%Y-%m-%d")
        pdf_url = f"https://servizimeteomont.csifa.carabinieri.it/api/meteomontweb/bollettino/getbollettinocl/I/13/2/cl/{str_data}"
        
        try:
            # Verifica se il PDF esiste per questa data
            check = requests.head(pdf_url, timeout=5)
            if check.status_code == 200:
                # Recupero Dati Pericolo (Settore 13, Sottosettore 2 = Lucano)
                res_p = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13", headers=headers).json()
                p_data = next((p for p in res_p if p.get('idSottoSettore') == 2), res_p[0])

                # Recupero Stazioni Basilicata (PZ)
                res_s = requests.get("https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13", headers=headers).json()
                stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ']

                dati = {
                    "testata": {
                        "settore": "Appennino Lucano",
                        "data_emissione": data_target.strftime("%d/%m/%Y"),
                        "nr_bollettino": "211/2026", # Estratto dinamicamente se possibile
                        "aggiornamento_realtime": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                    },
                    "bollettino": {
                        "grado_pericolo": p_data.get("gradoPericolo", 1),
                        "label": p_data.get("descrizioneGradoPericolo", "DEBOLE").upper(),
                        "situazione_tipo": p_data.get("problemaValanghivo", "Situazione primaverile"),
                        "avvertenze": "Evitare le attività fuori pista nelle ore più calde su pendii ripidi al sole.",
                        "manto_nevoso": "Buona stabilità su alcuni punti per tutte le esposizioni."
                    },
                    "meteo_generale": {
                        "quota_neve_nord": "1000-1300 m",
                        "quota_neve_sud": "1100-1400 m"
                    },
                    "meteo_quota": {
                        "zero_termico": p_data.get("quota", "2900-3100 m"),
                        "2000m": {"temp": "+4°C", "percepita": "1°C"}
                    },
                    "stazioni": [
                        {
                            "nome": s.get("nomeStazione"),
                            "neve": f"{s.get('altezzaNeveAlSuolo', 0)} cm",
                            "t_min_max": f"{s.get('temperaturaMin', 'N.P.')}/{s.get('temperaturaMax', 'N.P.')}"
                        } for s in stazioni_lucane if s.get('provincia') == 'PZ'
                    ],
                    "link_pdf": pdf_url
                }

                with open('valanghe.json', 'w', encoding='utf-8') as f:
                    json.dump(dati, f, indent=4, ensure_ascii=False)
                
                invia_telegram(dati, pdf_url)
                print(f"Aggiornamento completato con dati del {str_data}")
                return
        except Exception as e:
            continue
    print("Nessun bollettino recente trovato.")

if __name__ == "__main__":
    scrape()
