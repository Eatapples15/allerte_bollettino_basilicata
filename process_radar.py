import json
import os
import requests
from datetime import datetime, timedelta

# Configurazione
OUTPUT_RADAR = 'radar_live.geojson'

def get_latest_radar_url():
    # Il radar DPC pubblica ogni 10 minuti. Calcoliamo l'ultimo slot disponibile (UTC)
    now = datetime.utcnow() - timedelta(minutes=15) # Buffer di 15 min per sicurezza
    minute = (now.minute // 10) * 10
    timestamp = now.replace(minute=minute, second=0, microsecond=0)
    
    # Formato data per URL: DD-MM-YYYY-HH-mm
    str_time = timestamp.strftime("%d-%m-%Y-%H-%M")
    
    # Nota: I link S3 diretti del DPC spesso richiedono firma o sono accessibili via API.
    # Usiamo il repository pubblico mirror o la logica di puntamento dinamico.
    # Se hai un token fisso lo inseriamo, altrimenti puntiamo al Mosaico Nazionale VMI.
    base_url = f"https://raw.githubusercontent.com/pcm-dpc/DPC-Mappe/main/allertamento/radar/last/VMI.json"
    return base_url

def download_and_vectorize():
    try:
        # Invece di processare un TIF pesante (che richiederebbe librerie GIS complesse su GitHub),
        # sfruttiamo il JSON pre-elaborato che il DPC pubblica per le sue mappe web.
        # È il modo più veloce e "a colpo sicuro" per WebSOR.
        response = requests.get("https://raw.githubusercontent.com/pcm-dpc/DPC-Mappe/main/allertamento/radar/last/VMI.json", timeout=15)
        if response.status_code == 200:
            radar_data = response.json()
            
            # Salviamo il file nella nostra repo arricchendolo con un campo colore per WebSOR
            for feature in radar_data.get('features', []):
                valore = feature['properties'].get('value', 0)
                # Mappatura colori radar (DBZ)
                if valore < 20: color = "#00fbff" # Pioggia debole
                elif valore < 35: color = "#0000ff" # Moderata
                elif valore < 45: color = "#ffff00" # Forte
                else: color = "#ff0000" # Estrema
                
                feature['properties']['colore_radar'] = color

            with open(OUTPUT_RADAR, 'w', encoding='utf-8') as f:
                json.dump(radar_data, f)
            print("Radar aggiornato con successo.")
            return True
    except Exception as e:
        print(f"Errore Radar: {e}")
        return False

if __name__ == "__main__":
    download_and_vectorize()
