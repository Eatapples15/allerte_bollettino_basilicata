import json
import os

# Nomi dei file basati sulla tua repo
GEO_FILE = 'limits_R_17_municipalities.geojson'
DATA_FILE = 'dati_bollettino.json'
OUTPUT_FILE = 'bollettino_comunale_live.geojson'

def merge():
    if not os.path.exists(GEO_FILE) or not os.path.exists(DATA_FILE):
        print("Errore: Uno dei file sorgente non esiste!")
        return

    # Carica geografia
    with open(GEO_FILE, 'r', encoding='utf-8') as f:
        geo_data = json.load(f)

    # Carica dati bollettino
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        alert_data = json.load(f)

    # Mappa colori Protezione Civile
    color_map = {
        "VERDE": "#00ff00",
        "GIALLO": "#ffff00",
        "ARANCIONE": "#ff9900",
        "ROSSO": "#ff0000"
    }

    # Creiamo un dizionario per ricerca rapida (normalizziamo i nomi dei comuni)
    # Assumiamo che il tuo dati_bollettino.json sia una lista di { "comune": "...", "allerta": "..." }
    data_lookup = {item['comune'].upper().strip(): item['allerta'].upper() for item in alert_data}

    # Fusione
    for feature in geo_data['features']:
        # Il campo nel tuo geojson si chiama 'name'
        nome_comune = feature['properties'].get('name', '').upper().strip()
        
        allerta = data_lookup.get(nome_comune, "VERDE") # Default Verde se non trovato
        
        # Inseriamo le nuove proprietà per WebSOR
        feature['properties']['allerta_stato'] = allerta
        feature['properties']['colore_esadecimale'] = color_map.get(allerta, "#00ff00")

    # Salva il file finale
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(geo_data, f, ensure_ascii=False)
    
    print(f"Successo! Creato {OUTPUT_FILE}")

if __name__ == "__main__":
    merge()
