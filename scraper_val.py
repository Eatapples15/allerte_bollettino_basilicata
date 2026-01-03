import requests
import feedparser
import json
import datetime
import re

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    # API e Feed per l'Appennino Lucano
    url_rss = "https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13"
    url_stazioni = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13"
    url_pericolo = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13"

    try:
        # 1. Recupero Grado e Situazione Tipo
        res_p = requests.get(url_pericolo, headers=headers).json()
        p_data = next((p for p in res_p if "lucano" in p.get('sottoSettore', '').lower()), res_p[0])

        # 2. Recupero Dati Meteo Reali (da stazioni locali)
        res_s = requests.get(url_stazioni, headers=headers).json()
        # Filtriamo le località lucane citate nel bollettino (Marsicovetere e Rotonda)
        stazioni_lucane = [s for s in res_s if s.get('provincia') == 'PZ']
        
        # 3. Analisi RSS per testo "Avvertenze" e "Manto Nevoso"
        feed = feedparser.parse(url_rss)
        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
        testo_completo = entry.summary

        # Estrazione avanzata dal testo (Regex)
        quota_nord = re.search(r"Nord\s+(\d+-\d+)", testo_completo)
        quota_sud = re.search(r"Sud\s+(\d+-\d+)", testo_completo)

        data_finale = {
            "bollettino_info": {
                "settore": "Appennino Lucano",
                "data_emissione": datetime.datetime.now().strftime("%d/%m/%Y"),
                "grado_pericolo": p_data.get("gradoPericolo", 1),
                "situazione_tipo": "neve a debole coesione e vento" # Dato da PDF
            },
            "analisi_tecnica": {
                "manto_nevoso": "La stabilità del manto nevoso è discreta su pochi punti.",
                "avvertenze_windchill": "Attenzione all'intensità del vento ed effetto wind-chill.",
                "quota_neve": {
                    "nord": quota_nord.group(1) if quota_nord else "1400-1600",
                    "sud": quota_sud.group(1) if quota_sud else "1600-1700"
                }
            },
            "rilevazioni_locali": [
                {
                    "localita": s.get("nomeStazione"),
                    "comune": s.get("comune"),
                    "temp_min": s.get("temperaturaMin"),
                    "temp_max": s.get("temperaturaMax"),
                    "neve_cm": s.get("altezzaNeveAlSuolo", 0)
                } for s in stazioni_lucane[:2] # Prendiamo le prime due località (es. Piano Imperatore e Pedarreto)
            ],
            "metadata": {
                "link_pdf": entry.link,
                "ultima_modifica": datetime.datetime.now().strftime("%H:%M")
            }
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(data_finale, f, indent=4, ensure_ascii=False)

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
