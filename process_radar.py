import requests
import json
import os
import time
from datetime import datetime

# Import critici con controllo
try:
    import xarray as xr
    import pandas as pd
    import cfgrib
except ImportError as e:
    print(f"❌ Errore: Librerie mancanti nel requirements.txt! ({e})")
    exit(1)

# URL principali
GRIB_URL = "https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/latest"
OUTPUT_FILE = "radar_data.json"

def download_file(url, max_retries=3):
    """Tenta il download con sistema di retry per evitare l'errore 404 momentaneo"""
    for i in range(max_retries):
        try:
            print(f"📥 Tentativo {i+1}: Download file GRIB...")
            r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
            
            if r.status_code == 200 and len(r.content) > 10000:
                with open("temp_radar.grib", "wb") as f:
                    f.write(r.content)
                print(f"✅ File scaricato con successo ({len(r.content)} bytes)")
                return True
            else:
                print(f"⚠️ Risposta server: {r.status_code}. Il file potrebbe non essere pronto.")
        except Exception as e:
            print(f"❌ Errore durante il download: {e}")
        
        if i < max_retries - 1:
            print("Wait 15 secondi e riprovo...")
            time.sleep(15)
    return False

def process():
    if not download_file(GRIB_URL):
        print("❌ Impossibile scaricare il file dopo vari tentativi. Salto questo run.")
        return

    try:
        print("⚙️ Analisi GRIB in corso...")
        # Apertura dataset
        ds = xr.open_dataset("temp_radar.grib", engine="cfgrib", backend_kwargs={'indexpath': ''})
        
        # Identificazione variabile
        var_name = list(ds.data_vars)[0]
        print(f"🔍 Variabile rilevata: {var_name}")

        # Coordinate Basilicata (Ritaglio per RAM)
        lat_min, lat_max = 39.9, 41.2
        lon_min, lon_max = 15.2, 17.2

        lat_key = 'latitude' if 'latitude' in ds.coords else 'lat'
        lon_key = 'longitude' if 'longitude' in ds.coords else 'lon'

        # Ritaglio area prima della conversione
        ds_cropped = ds.sel({
            lat_key: slice(lat_max, lat_min), 
            lon_key: slice(lon_min, lon_max)
        })

        # Conversione in DataFrame
        df = ds_cropped[var_name].to_dataframe().reset_index()
        
        # Filtro pioggia > 0.2 mm/h
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

        print(f"✅ Successo! Trovati {len(radar_points)} punti pioggia.")

    except Exception as e:
        print(f"❌ Errore durante l'elaborazione: {e}")
        # Creiamo un file minimo per evitare errori nei workflow successivi
        if not os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "w") as f:
                json.dump({"last_update": datetime.now().strftime("%d/%m/%Y %H:%M"), "points": []}, f)
    
    finally:
        # Pulizia file temporanei
        for f in ["temp_radar.grib", "temp_radar.grib.923a8.idx"]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    process()
