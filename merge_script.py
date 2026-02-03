import json
import os

# Configurazione file
GEO_FILE = 'limits_R_17_municipalities.geojson'
DATA_FILE = 'dati_bollettino.json'
OUTPUT_FILE = 'bollettino_comunale_live.geojson'

def merge():
    # Verifica esistenza file
    if not os.path.exists(GEO_FILE) or not os.path.exists(DATA_FILE):
        print("Errore: File sorgente mancanti.")
        return

    # Caricamento dati
    with open(GEO_FILE, 'r', encoding='utf-8') as f:
        geo_data = json.load(f)
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        alert_data = json.load(f)

    # Mappa colori standard Protezione Civile
    color_map = {
        "VERDE": "#00ff00",
        "GIALLO": "#ffff00",
        "ARANCIONE": "#ff9900",
        "ROSSO": "#ff0000",
        "BIANCO": "#ffffff"
    }

    # NORMALIZZAZIONE DATI (Risolve l'errore TypeError)
    # Gestiamo sia se alert_data è una lista, sia se è un dizionario
    data_lookup = {}
    
    if isinstance(alert_data, dict):
        # Se il JSON è {"POTENZA": "ROSSO", ...}
        for k, v in alert_data.items():
            valore_allerta = v.upper() if isinstance(v, str) else v.get('allerta', 'VERDE').upper()
            data_lookup[k.upper().strip()] = valore_allerta
    elif isinstance(alert_data, list):
        # Se il JSON è [{"comune": "POTENZA", "allerta": "ROSSO"}, ...]
        for item in alert_data:
            if isinstance(item, dict):
                nome = item.get('comune', '').upper().strip()
                stato = item.get('allerta', 'VERDE').upper()
                data_lookup[nome] = stato

    # FUSIONE GEOGRAFICA
    for feature in geo_data['features']:
        # Cerchiamo il nome del comune nelle proprietà del GeoJSON
        # Nota: controlla se il campo nel geojson è 'name', 'COMUNE' o 'nome'
        props = feature['properties']
        nome_comune = props.get('name', props.get('COMUNE', '')).upper().strip()
        
        # Recupero allerta (default VERDE se non trovato)
        stato_allerta = data_lookup.get(nome_comune, "VERDE")
        
        # Iniezione dati nel GeoJSON finale
        feature['properties']['allerta_oggi'] = stato_allerta
        feature['properties']['colore_web'] = color_map.get(stato_allerta, "#00ff00")

    # Salvataggio
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(geo_data, f, ensure_ascii=False, indent=2)
    
    print(f"Merge completato con successo: {OUTPUT_FILE}")

if __name__ == "__main__":
    merge()
