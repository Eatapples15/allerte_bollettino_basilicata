import json
import os

# Configurazione file
GEO_FILE = 'limits_R_17_municipalities.geojson'
DATA_FILE = 'dati_bollettino.json'
OUTPUT_FILE = 'bollettino_comunale_live.geojson'

def merge():
    if not os.path.exists(GEO_FILE) or not os.path.exists(DATA_FILE):
        print("Errore: File sorgente mancanti.")
        return

    # Caricamento
    with open(GEO_FILE, 'r', encoding='utf-8') as f:
        geo_data = json.load(f)
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        alert_data = json.load(f)

    # Mappa colori basata sui valori del tuo JSON (green, yellow, orange, red)
    color_map = {
        "green": "#00ff00",
        "yellow": "#ffff00",
        "orange": "#ff9900",
        "red": "#ff0000"
    }

    # Accediamo alla sezione "zone" del tuo bollettino
    zone_alerts = alert_data.get('zone', {})

    for feature in geo_data['features']:
        props = feature['properties']
        
        # Identifica il campo nel tuo GeoJSON che contiene la zona (BASI A1, BASI B, etc.)
        # Solitamente nei file della Regione Basilicata è 'zona' o 'ZONA_ALLERTA'
        # Se il campo ha un nome diverso, cambialo qui sotto:
        id_zona = props.get('zona') or props.get('ZONA') or props.get('zona_allerta')
        
        if id_zona:
            id_zona = id_zona.strip()
            info = zone_alerts.get(id_zona)
            
            if info:
                colore_testo = info.get('oggi', 'green')
                # Inseriamo le proprietà che WebSOR userà per colorare e mostrare i dati
                feature['properties']['allerta_oggi'] = colore_testo
                feature['properties']['colore_web'] = color_map.get(colore_testo, "#00ff00")
                feature['properties']['rischio_oggi'] = info.get('rischio_oggi', '')
            else:
                # Default se la zona non viene trovata nel bollettino
                feature['properties']['allerta_oggi'] = "green"
                feature['properties']['colore_web'] = "#00ff00"
        else:
            # Se il comune nel GeoJSON non ha l'attributo della zona
            feature['properties']['allerta_oggi'] = "unknown"
            feature['properties']['colore_web'] = "#cccccc"

    # Salvataggio del file finale arricchito
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(geo_data, f, ensure_ascii=False, indent=2)
    
    print(f"Mappa aggiornata con successo in: {OUTPUT_FILE}")

if __name__ == "__main__":
    merge()
