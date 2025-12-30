
import requests
import json
import datetime

def scrape():
    # Endpoint forniti
    url_stazione = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/datistazione/17"
    url_pericolo = "https://servizimeteomont.csifa.carabinieri.it/api/news/json/gradopericolo/13"
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        # 1. Recupero dati stazione (Neve al suolo, Temp, Vento)
        res_stazione = requests.get(url_stazione, headers=headers)
        dati_stazione = res_stazione.json()[0] if res_stazione.json() else {}

        # 2. Recupero grado pericolo strutturato
        res_pericolo = requests.get(url_pericolo, headers=headers)
        dati_pericolo = res_pericolo.json()[0] if res_pericolo.json() else {}

        # 3. Assemblaggio JSON finale
        json_finale = {
            "settore": "Appennino Lucano",
            "stazione_riferimento": dati_stazione.get("nomeStazione", "N/D"),
            "data_osservazione": dati_stazione.get("dataOraOsservazione", "N/D"),
            
            # Dati Neve e Meteo (dalla stazione ID 17)
            "meteo": {
                "neve_suolo_cm": dati_stazione.get("altezzaNeveAlSuolo", 0),
                "neve_fresca_cm": dati_stazione.get("altezzaNeveFresca24h", 0),
                "temp_aria": dati_stazione.get("temperaturaAria", "N/D"),
                "vento_velocita": dati_stazione.get("velocitaVento", "N/D"),
                "vento_direzione": dati_stazione.get("direzioneVento", "N/D")
            },
            
            # Dati Pericolo (dall'ID 13)
            "valanghe": {
                "grado_pericolo": dati_pericolo.get("gradoPericolo", "N/D"),
                "tendenza": dati_pericolo.get("tendenza", "N/D"),
                "problema": dati_pericolo.get("problemaValanghivo", "N/D"),
                "quota": dati_pericolo.get("quota", "N/D")
            },
            
            "last_update": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        }

        with open('valanghe.json', 'w', encoding='utf-8') as f:
            json.dump(json_finale, f, indent=4, ensure_ascii=False)
        
        print("Sincronizzazione API completata.")

    except Exception as e:
        print(f"Errore durante lo scraping: {e}")

if __name__ == "__main__":
    scrape()
