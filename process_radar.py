import requests
import json
import os
import time
from datetime import datetime, timedelta

try:
    import xarray as xr
    import pandas as pd
    import cfgrib
except ImportError as e:
    print(f"❌ Librerie mancanti: {e}")
    exit(1)

# CONFIGURAZIONE
DATASET_ID = "radar_dpc"
API_BASE = "https://meteohub.agenziaitaliameteo.it/api/v1"
OUTPUT_FILE = "radar_data.json"

def get_latest_file_url():
    """Prova diverse strategie per trovare l'ultimo file GRIB disponibile"""
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    
    # STRATEGIA 1: Interrogazione Catalogo File (La più precisa)
    try:
        print(f"🔍 Strategia 1: Ricerca nel catalogo file per {DATASET_ID}...")
        url = f"{API_BASE}/datasets/{DATASET_ID}/files"
        # Cerchiamo file completati, ordinati per creazione
        params = {"limit": 5, "sort": "-created", "status": "COMPLETED"}
        r = requests.get(url, params=params, headers=headers, timeout=20)
        
        if r.status_code == 200:
            files = r.json()
            if files and len(files) > 0:
                f_id = files[0]['id']
                print(f"✅ File trovato nel catalogo: {f_id}")
                return f"{API_BASE}/datasets/{DATASET_ID}/files/{f_id}/download"
    except Exception as e:
        print(f"⚠️ Strategia 1 fallita: {e}")

    # STRATEGIA 2: Elenco OpenData (Quella che usavi tu, ma con correzione)
    try:
        print(f"🔍 Strategia 2: Ricerca in opendata list...")
        url = f"https://meteohub.agenziaitaliameteo.it/api/datasets/{DATASET_ID}/opendata"
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                # Se è una lista di dizionari, prendi il 'name' dell'ultimo
                data.sort(key=lambda x: x.get('name', '') if isinstance(x, dict) else x, reverse=True)
                item = data[0]
                fname = item.get('name') if isinstance(item, dict) else item
                print(f"✅ File trovato in opendata: {fname}")
                return f"https://meteohub.agenziaitaliameteo.it/api/opendata/{fname}"
    except Exception as e:
        print(f"⚠️ Strategia 2 fallita: {e}")

    # STRATEGIA 3: Fallback Ultima Spiaggia (Latest)
    print("⚠️ Strategia 3: Tentativo link generico 'latest'...")
    return f"{API_BASE}/datasets/{DATASET_ID}/latest/download"

def download_radar(url):
    print(f"📥 Download da: {url}")
    try:
        r = requests.get(url, timeout=120, stream=True, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            with open("temp_radar.grib", "wb") as f:
                f.write(r.content)
            size = os.path.getsize("temp_radar.grib")
            if size > 15000:
                print(f"✅ Download OK: {size} bytes")
                return True
        print(f"⚠️ Errore download: Status {r.status_code}")
    except Exception as e:
        print(f"❌ Eccezione download: {e}")
    return False

def process():
    target_url = get_latest_file_url()
    
    if not download_radar(target_url):
        print("❌ Nessun dato radar recuperato. Probabile manutenzione server DPC.")
        return

    try:
        print("⚙️ Analisi GRIB con xarray...")
        ds = xr.open_dataset("temp_radar.grib", engine="cfgrib", backend_kwargs={'indexpath': ''})
        var_name = list(ds.data_vars)[0]
        
        # Area Basilicata
        lat_min, lat_max = 39.9, 41.2
        lon_min, lon_max = 15.2, 17.2

        lat_key = 'latitude' if 'latitude' in ds.coords else 'lat'
        lon_key = 'longitude' if 'longitude' in ds.coords else 'lon'

        # Slice geografico
        ds_cropped = ds.sel({
            lat_key: slice(lat_max, lat_min), 
            lon_key: slice(lon_min, lon_max)
        })

        df = ds_cropped[var_name].to_dataframe().reset_index()
        df_filtered = df[df[var_name] > 0.2].dropna()

        radar_points = []
        for _, row in df_filtered.iterrows():
            radar_points.append({
                "lat": round(float(row[lat_key]), 3),
                "lon": round(float(row[lon_key]), 3),
                "val": round(float(row[var_name]), 2)
            })

        output = {
            "last_update": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "count": len(radar_points),
            "points": radar_points
        }

        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        print(f"✅ Completato! Punti rilevati: {len(radar_points)}")

    except Exception as e:
        print(f"❌ Errore analisi: {e}")
    finally:
        for f in ["temp_radar.grib", "temp_radar.grib.923a8.idx"]:
            if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    process()
