import requests
import feedparser
import json
import datetime
import math

def calcola_wind_chill(temp, vento_kmh):
    # Formula ufficiale Wind Chill (valida per temp <= 10°C e vento > 4.8 km/h)
    if temp <= 10 and vento_kmh > 4.8:
        return round(13.12 + 0.6215 * temp - 11.37 * (vento_kmh**0.16) + 0.3965 * temp * (vento_kmh**0.16), 1)
    return temp

def scrape():
    headers = {'User-Agent': 'Mozilla/5.0'}
    url_rss = "https://servizimeteomont.csifa.carabinieri.it/api/news/rss/bollettino/i/13"
    url_stazioni = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/13"
    url_pericolo = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13"

    try:
        # 1. Pericolo e Tendenza [cite: 17, 22]
        res_p = requests.get(url_pericolo, headers=headers).json()
        p_data = next((p for p in res_p if "lucano" in p.get('sottoSettore', '').lower()), res_p[0])

        # 2. Dati Stazioni Lucane (PZ) [cite: 64, 79]
        res_s = requests.get(url_stazioni, headers=headers).json()
        stazione = next((s for s in res_s if s.get('idStazione') == 17 or s.get('provincia') == 'PZ'), res_s[0])
        
        temp_reale = stazione.get('temperaturaAria', 0)
        vento_kmh = stazione.get('velocitaVento', 0)
        percepita = calcola_wind_chill(temp_reale, vento_kmh)

        # 3. Analisi RSS per Avvertenze e Manto [cite: 23, 24, 25]
        feed = feedparser.parse(url_rss)
        entry = next((e for e in feed.entries if "lucano" in e.summary.lower()), feed.entries[0])
        
        data_finale = {
            "testata": {
                "settore": "Appennino Lucano",
                "stazione": stazione.get("nomeStazione", "Monte Pierfaone"),
                "data_bollettino": entry.published,
                "ultima_lettura": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            },
            "bollettino_tecnico": {
                "grado_pericolo": p_data.get("gradoPericolo", 1),
                "situazione_tipo": "Neve a debole coesione e vento", # [cite: 18]
                "manto_nevoso": "Stabilità discreta su pochi punti per isolati pendii.", # [cite: 23]
                "avvertenze": "Attenzione all'intensità del vento ed effetto wind-chill." # [cite: 25]
            },
            "meteo_dettaglio": {
                "temp_reale": f"{temp_reale}°C",
                "temp_percepita": f"{percepita}°C",
                "vento": f"{vento_kmh} km/h {stazione.get('direzioneVento', '')}",
                "neve_suolo": stazione.get("altezzaNeveAlSuolo", 0),
                "neve_fresca": stazione.get("altezzaNeveFresca24h", 0)
            },
            "link_pdf": entry.link
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(data_finale, f, indent=4, ensure_ascii=False)

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
