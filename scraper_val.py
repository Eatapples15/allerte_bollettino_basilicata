import requests
import json
import datetime

def scrape():
    # URL dei dati stazione (Monte Pierfaone - Basilicata)
    url_stazione = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/17"
    # URL del grado pericolo (Settore Campano-Lucano)
    url_pericolo = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13"
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        # Recupero dati stazione (Basilicata)
        res_stazione = requests.get(url_stazione, headers=headers)
        # Prendiamo solo l'elemento della stazione 17
        lista_stazioni = res_stazione.json()
        dati_stazione = next((s for s in lista_stazioni if s.get('idStazione') == 17), lista_stazioni[0] if lista_stazioni else {})

        # Recupero grado pericolo
        res_pericolo = requests.get(url_pericolo, headers=headers)
        dati_pericolo = res_pericolo.json()[0] if res_pericolo.json() else {}

        json_finale = {
            "regione": "Basilicata",
            "zona": "Appennino Lucano",
            "stazione_nome": "Monte Pierfaone (PZ)",
            "quota_stazione": "1732 m",
            "data_osservazione": dati_stazione.get("dataOraOsservazione", "N/D"),
            
            "meteo": {
                "neve_suolo": dati_stazione.get("altezzaNeveAlSuolo", 0),
                "neve_fresca_24h": dati_stazione.get("altezzaNeveFresca24h", 0),
                "temperatura": dati_stazione.get("temperaturaAria", "N/D"),
                "vento_vel": dati_stazione.get("velocitaVento", "N/D"),
                "vento_dir": dati_stazione.get("direzioneVento", "N/D")
            },
            
            "pericolo": {
                "grado": dati_pericolo.get("gradoPericolo", "N/D"),
                "tendenza": dati_pericolo.get("tendenza", "N/D"),
                "problema": dati_pericolo.get("problemaValanghivo", "N/D"),
                "testo_quota": dati_pericolo.get("quota", "N/D")
            },
            
            "aggiornamento_sistema": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(json_finale, f, indent=4, ensure_ascii=False)
        
        print(f"Dati aggiornati per {json_finale['stazione_nome']}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
