import requests
import json
import os
from datetime import datetime

# Import critici con controllo
try:
    import xarray as xr
    import pandas as pd
    import cfgrib
except ImportError as e:
    print(f"❌ Errore: Librerie mancanti nel requirements.txt! ({e})")
    exit(1)

GRIB_URL = "https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/latest"
OUTPUT_FILE = "radar_data.json"

def process():
    try:
        print("📥 Download file GRIB dal Radar DPC...")
        r = requests.get(GRIB_URL, timeout=120)
        if r.status_code != 200:
            print(f"❌ Errore download: {r.status_code}")
            return

        with open("temp_radar.grib", "wb") as f:
            f.write(r.content)
        
        print(f"📦 File scaricato: {os.path.getsize('temp_radar.grib')} bytes")

        # Apertura dataset
        # backend_kwargs={'indexpath': ''} evita tentativi di scrittura indici su disco
        ds = xr.open_dataset("temp_radar.grib", engine="cfgrib", backend_kwargs={'indexpath': ''})
        
        # Identificazione variabile (solitamente SRI)
        var_name = list(ds.data_vars)[0]
        print(f"🔍 Variabile rilevata: {var_name}")

        # Coordinate Basilicata (Ritaglio per risparmiare RAM)
        lat_min, lat_max = 39.9, 41.2
        lon_min, lon_max = 15.2, 17.2

        # Rilevamento nomi coordinate
        lat_key = 'latitude' if 'latitude' in ds.coords else 'lat'
        lon_key = 'longitude' if 'longitude' in ds.coords else 'lon'

        print(f"✂️ Ritaglio area Basilicata...")
        # Il radar nazionale è enorme, tagliamo prima di convertire in DataFrame
        ds_cropped = ds.sel({
            lat_key: slice(lat_max, lat_min), 
            lon_key: slice(lon_min, lon_max)
        })

        # Conversione in DataFrame
        df = ds_cropped[var_name].to_dataframe().reset_index()
        
        # Filtro: pioggia > 0.2 mm/h e rimozione dati nulli
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
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"last_update": datetime.now().strftime("%d/%m/%Y %H:%M"), "points": []}, f)
    
    finally:
        # Pulizia file temporanei
        for f in ["temp_radar.grib", "temp_radar.grib.923a8.idx"]:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    process()
