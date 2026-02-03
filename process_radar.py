import json
import requests
import datetime
import os

# Configurazione
# Usiamo il VMI (Vertical Maximum Intensity) che è il più utile per i temporali
RADAR_SOURCE_URL = "https://raw.githubusercontent.com/pcm-dpc/DPC-Mappe/main/allertamento/radar/last/VMI.json"
OUTPUT_FILE = 'radar_data.json'

def process_radar():
    print(f"Inizio elaborazione radar alle {datetime.datetime.now()}")
    
    try:
        # 1. Scarica il dato
        response = requests.get(RADAR_SOURCE_URL, timeout=20)
        response.raise_for_status()
        radar_geojson = response.json()
        
        # 2. Arricchimento dati per WebSOR
        # Aggiungiamo un timestamp per forzare il commit di Git ed evitare il "nothing to commit"
        radar_geojson['metadata'] = {
            "last_updated": datetime.datetime.now().isoformat(),
            "source": "DPC Nazionale",
            "region": "Basilicata Focus"
        }

        # 3. Logica Colori (se non presente nel file sorgente)
        for feature in radar_geojson.get('features', []):
            val = feature['properties'].get('value', 0)
            # Scala riflettività/intensità tipica
            if val <= 10: color = "#00ecec" # Pioviggine
            elif val <= 25: color = "#01a0f6" # Pioggia debole
            elif val <= 35: color = "#0000f6" # Moderata
            elif val <= 45: color = "#e7c000" # Forte
            elif val <= 55: color = "#ff9000" # Molto forte
            else: color = "#ff0000"           # Estrema/Grandine
            
            feature['properties']['fill'] = color
            feature['properties']['fill-opacity'] = 0.6

        # 4. Salvataggio
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(radar_geojson, f, ensure_ascii=False)
        
        print(f"Successo: {OUTPUT_FILE} generato con {len(radar_geojson.get('features', []))} celle radar.")
        return True

    except Exception as e:
        print(f"ERRORE CRITICO: Impossibile aggiornare il radar. Dettaglio: {e}")
        return False

if __name__ == "__main__":
    process_radar()
