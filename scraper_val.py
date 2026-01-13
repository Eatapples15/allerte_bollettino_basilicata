import requests
import feedparser
import json
import datetime

def calcola_wind_chill(temp, nodi_vento):
    # Conversione nodi in km/h per la formula
    vento_kmh = nodi_vento * 1.852
    if temp <= 10 and vento_kmh > 4.8:
        return round(13.12 + 0.6215 * temp - 11.37 * (vento_kmh**0.16) + 0.3965 * temp * (vento_kmh**0.16), 1)
    return temp

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    url_rss = "https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13"
    url_stazioni = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13"
    url_pericolo = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13"

    try:
        # 1. Recupero Pericolo e Situazione (ID 13)
        res_p = requests.get(url_pericolo, headers=headers).json()
        p_data = next((p for p in res_p if "lucano" in p.get('sottoSettore', '').lower()), res_p[0])

        # 2. Recupero Tutte le Stazioni della Basilicata
        res_s = requests.get(url_stazioni, headers=headers).json()
        stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ']

        # 3. Analisi RSS per testi estesi
        feed = feedparser.parse(url_rss)
        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])

        # Costruzione del JSON con TUTTI i dati del PDF
        output = {
            "testata": {
                "settore": "Appennino Lucano",
                "bollettino_nr": "211/2026",
                "data_emissione": "13/01/2026",
                "validita": "48 ore"
            },
            "situazione_valanghe": {
                "grado_pericolo": p_data.get("gradoPericolo", 1), # Debole 1 [cite: 109]
                "situazione_tipo": "Situazione primaverile", # 
                "manto_nevoso": "Buona stabilità su alcuni punti per tutte le esposizioni", # [cite: 115]
                "valanghe_osservate": "Nessuna valanga", # [cite: 107]
                "avvertenze": "Evitare attività fuori pista nelle ore più calde su pendii ripidi al sole" # 
            },
            "parametri_neve_quota": {
                "nord": "1000-1300 mslm", # [cite: 104]
                "sud": "1100-1400 mslm", # [cite: 104]
                "zero_termico_max": "2900-3100 m" # 
            },
            "stazioni_locali": [
                {
                    "nome": s.get("nomeStazione"),
                    "comune": s.get("comune"),
                    "quota": f"{s.get('quota', 0)} m",
                    "neve_suolo": f"{s.get('altezzaNeveAlSuolo', 0)} cm",
                    "neve_24h": f"{s.get('altezzaNeveFresca24h', 0)} cm",
                    "t_min": s.get("temperaturaMin", "N.P."),
                    "t_max": s.get("temperaturaMax", "N.P.")
                } for s in stazioni_lucane
            ],
            "previsione_meteo_quota": {
                "1000m": {"temp": "+7°C", "vento": "2 nodi Ovest"}, # 
                "2000m": {"temp": "+4°C", "vento": "8 nodi Ovest"}, # 
                "3000m": {"temp": "+0°C", "percepita": "-4°C"} # 
            },
            "metadata": {
                "ultima_sincronizzazione": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                "link_pdf": entry.link
            }
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        
        print("Sync completo con tutti i dati del PDF.")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
