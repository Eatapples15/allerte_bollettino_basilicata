import requests
import xarray as xr
import json
import os
import pandas as pd
from datetime import datetime

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

        # Apertura dataset con xarray
        ds = xr.open_dataset("temp_radar.grib", engine="cfgrib", backend_kwargs={'indexpath': ''})
        
        # Identificazione automatica variabile pioggia
        var_name = list(ds.data_vars)[0]
        print(f"🔍 Variabile rilevata: {var_name}")

        # RITAGLIO GEOGRAFICO IMMEDIATO (Riduce l'uso della RAM del 90%)
        # Coordinate Basilicata estese
        lat_min, lat_max = 39.9, 41.2
        lon_min, lon_max = 15.2, 17.2

        # Cerchiamo i nomi corretti delle coordinate (possono essere latitude/longitude o lat/lon)
        lat_key = 'latitude' if 'latitude' in ds.coords else 'lat'
        lon_key = 'longitude' if 'longitude' in ds.coords else 'lon'

        print(f"✂️ Ritaglio area Basilicata (usando {lat_key}/{lon_key})...")
        
        # Slice del dataset prima della conversione in DataFrame
        ds_cropped = ds.sel({
            lat_key: slice(lat_max, lat_min), # Nota: nei GRIB la latitudine spesso è decrescente
            lon_key: slice(lon_min, lon_max)
        })

        # Conversione in DataFrame del solo ritaglio
        df = ds_cropped[var_name].to_dataframe().reset_index()
        
        # Filtro: pioggia > 0.2 mm/h e rimozione NaN
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

        print(f"✅ Completato! Trovati {len(radar_points)} punti pioggia in Basilicata.")

    except Exception as e:
        print(f"❌ Errore: {e}")
        # Manteniamo la struttura del file per non rompere la mappa
        if not os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "w") as f:
                json.dump({"last_update": datetime.now().strftime("%d/%m/%Y %H:%M"), "points": []}, f)
    finally:
        if os.path.exists("temp_radar.grib"):
            os.remove("temp_radar.grib")
        # Rimuoviamo anche eventuali file indice creati da cfgrib
        if os.path.exists("temp_radar.grib.923a8.idx"):
            os.remove("temp_radar.grib.923a8.idx")

if __name__ == "__main__":
    process()
