import requests
import json
import re
import time
import os
import sys

# CONFIGURAZIONE
INPUT_FILE = "dati_sensori.json"
OUTPUT_FILE = "anagrafica_stazioni.json"
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/stazione.php"

FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def dms_to_decimal(dms_str):
    """Converte una stringa come 40° 9' 39" N in float decimale"""
    try:
        # Pulisce la stringa da caratteri html e spazi extra
        clean = dms_str.replace("&nbsp;", " ").strip()
        
        # Regex per estrarre Gradi, Minuti, Secondi
        # Cerca 3 gruppi di numeri separati da qualsiasi cosa non numerica
        match = re.match(r"(\d+)\D+(\d+)\D+(\d+)", clean)
        
        if match:
            degrees = float(match.group(1))
            minutes = float(match.group(2))
            seconds = float(match.group(3))
            
            # Formula conversione DMS -> Decimale
            decimal = degrees + (minutes / 60) + (seconds / 3600)
            
            # Arrotonda a 6 cifre decimali (precisione GPS standard)
            return round(decimal, 6)
            
    except Exception as e:
        print(f"Errore conversione '{dms_str}': {e}")
    return None

def get_coordinates(station_id):
    url = f"{BASE_URL}?id={station_id}"
    try:
        r = requests.get(url, headers=FAKE_HEADERS, timeout=10)
        html = r.text
        
        # Regex per trovare le celle della tabella
        # Cerca: <th>Latitudine</th>...<td...>(CONTENUTO)</td>
        lat_match = re.search(r'<th>Latitudine<\/th>\s*<td[^>]*>(.*?)<\/td>', html, re.IGNORECASE | re.DOTALL)
        lon_match = re.search(r'<th>Longitudine<\/th>\s*<td[^>]*>(.*?)<\/td>', html, re.IGNORECASE | re.DOTALL)
        
        lat_dec = None
        lon_dec = None

        if lat_match:
            raw_lat = lat_match.group(1).strip() # Es: 40° 9' 39" N
            lat_dec = dms_to_decimal(raw_lat)
            
        if lon_match:
            raw_lon = lon_match.group(1).strip() # Es: 15° 59' 8" E
            lon_dec = dms_to_decimal(raw_lon)

        return lat_dec, lon_dec

    except Exception as e:
        print(f"❌ Errore connessione ID {station_id}: {e}")
    
    return None, None

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Errore: {INPUT_FILE} mancante.")
        sys.exit(1)

    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)

    # Estrazione ID unici
    unique_ids = set()
    for cat in data["sensori"].values():
        for s in cat["dati"]:
            if s.get("id"): unique_ids.add(s["id"])
    
    print(f"📋 Stazioni da analizzare: {len(unique_ids)}")
    
    # Caricamento cache esistente
    existing_coords = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r') as f:
                temp = json.load(f)
                for item in temp: existing_coords[item['id']] = item
        except: pass

    final_list = []
    count = 0
    new_found = 0
    
    for sid in unique_ids:
        count += 1
        
        # Se già presente e valido, salta
        if sid in existing_coords:
            final_list.append(existing_coords[sid])
            continue

        print(f"[{count}/{len(unique_ids)}] ID {sid}...", end=" ", flush=True)
        
        lat, lon = get_coordinates(sid)
        
        if lat and lon:
            print(f"✅ OK: {lat}, {lon}")
            item = {"id": sid, "lat": lat, "lon": lon}
            final_list.append(item)
            existing_coords[sid] = item # Aggiorna cache in memoria
            new_found += 1
        else:
            print(f"⚠️ Dati non trovati nella tabella.")
        
        time.sleep(0.3) # Leggero ritardo anti-ban

    # Salvataggio finale
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(final_list, f, indent=4)
    
    print(f"\n🌍 Finito! Coordinate salvate in {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
