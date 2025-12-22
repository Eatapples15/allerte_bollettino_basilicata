import requests
import json
import re
import time
import os
import sys

# File di input (i sensori trovati) e output (le coordinate)
INPUT_FILE = "dati_sensori.json"
OUTPUT_FILE = "anagrafica_stazioni.json"
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/stazione.php"

FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_coordinates(station_id):
    """Scarica la pagina della stazione e cerca le coordinate lat/lon"""
    url = f"{BASE_URL}?id={station_id}"
    try:
        r = requests.get(url, headers=FAKE_HEADERS, timeout=10)
        html = r.text
        
        # Cerca pattern di coordinate nell'HTML
        # Solitamente nei siti CFD sono dentro script di mappe tipo "setView([40.123, 16.123])"
        # o "LatLng(40.123, 16.123)"
        
        # Pattern 1: setView([lat, lon])
        match = re.search(r'setView\(\s*\[\s*([\d\.]+)\s*,\s*([\d\.]+)\s*\]', html)
        if match:
            return float(match.group(1)), float(match.group(2))
            
        # Pattern 2: LatLng(lat, lon)
        match = re.search(r'LatLng\(\s*([\d\.]+)\s*,\s*([\d\.]+)\s*\)', html)
        if match:
            return float(match.group(1)), float(match.group(2))

        # Pattern 3: Cerca testo in tabella "Latitudine ... Longitudine" (spesso in gradi sessagesimali, più complesso)
        # Per ora ci affidiamo ai dati della mappa che sono decimali e pronti all'uso.
        
    except Exception as e:
        print(f"❌ Errore ID {station_id}: {e}")
    
    return None, None

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Errore: {INPUT_FILE} non trovato. Esegui prima lo scraping dei sensori.")
        sys.exit(1)

    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)

    # Estrai tutti gli ID univoci
    unique_ids = set()
    for cat in data["sensori"].values():
        for s in cat["dati"]:
            if s.get("id"):
                unique_ids.add(s["id"])
    
    print(f"📋 Trovate {len(unique_ids)} stazioni uniche da geolocalizzare.")
    
    # Carica coordinate esistenti se ci sono (per non rifare tutto)
    existing_coords = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r') as f:
                temp = json.load(f)
                for item in temp:
                    existing_coords[item['id']] = item
            print(f"♻️ Recuperate {len(existing_coords)} coordinate già note.")
        except: pass

    final_list = []
    count = 0
    
    for sid in unique_ids:
        count += 1
        
        # Se l'abbiamo già, saltiamo (cache)
        if sid in existing_coords:
            final_list.append(existing_coords[sid])
            continue

        print(f"[{count}/{len(unique_ids)}] Geolocalizzo ID {sid}...", end=" ", flush=True)
        
        lat, lon = get_coordinates(sid)
        
        if lat and lon:
            print(f"✅ Trovato: {lat}, {lon}")
            final_list.append({"id": sid, "lat": lat, "lon": lon})
        else:
            print(f"⚠️ Non trovato.")
        
        # Pausa gentile per non farci bannare
        time.sleep(0.5)

    # Salvataggio
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(final_list, f, indent=4)
    
    print(f"\n🌍 Salvate {len(final_list)} coordinate in {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
