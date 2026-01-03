import requests
import json
import os
import time
from datetime import datetime

# Import scientifici
try:
    import xarray as xr
    import pandas as pd
    import cfgrib
except ImportError as e:
    print(f"❌ Librerie scientifiche mancanti: {e}")
    exit(1)

# NUOVA CONFIGURAZIONE METEOHUB OPENDATA
DATASET_ID = "radar_dpc"
LIST_URL = f"https://meteohub.agenziaitaliameteo.it/api/datasets/{DATASET_ID}/opendata"
DOWNLOAD_BASE = "https://meteohub.agenziaitaliameteo.it/api/opendata"
OUTPUT_FILE = "radar_data.json"

def get_latest_opendata_filename():
    """Interroga l'elenco opendata per trovare l'ultimo file caricato"""
    try:
        print(f"🔍 Recupero elenco file opendata per {DATASET_ID}...")
        r = requests.get(LIST_URL, timeout=30)
        if r.status_code == 200:
            files = r.json() # MeteoHub restituisce una lista di nomi file
            if files and isinstance(files, list):
                # I file solitamente hanno timestamp nel nome, prendiamo l'ultimo
                # Esempio nome: radar_dpc_202601031200.grib
                latest_file = sorted(files)[-1]
                print(f"✅ Ultimo file rilevato: {latest_file}")
                return latest_file
    except Exception as e:
        print(f"⚠️ Errore ricerca file: {e}")
    return None

def download_file(filename):
    url = f"{DOWNLOAD_BASE}/{filename}"
    print(f"📥 Download in corso: {url}")
    try:
        r = requests.get(url, timeout=120, stream=True)
        if r.status_code == 200:
            with open("temp_radar.grib", "wb") as f:
                f.write(r.content)
            size = os.path.getsize("temp_radar.grib")
            print(f"📦 Download completato ({size} bytes)")
            return size > 10000
    except Exception as e:
        print(f"❌ Errore download: {e}")
    return False

def process():
    filename = get_latest_opendata_filename()
    
    if not filename or not download_file(filename):
        print("❌ Impossibile ottenere il file GRIB.")
        return

    try:
        print("⚙️ Analisi GRIB con xarray...")
        # engine="cfgrib" richiede eccodes installato (presente nel tuo YAML)
        ds = xr.open_dataset("temp_radar.grib", engine="cfgrib", backend_kwargs={'indexpath': ''})
        
        var_name = list(ds.data_vars)[0]
        
        # Area Basilicata
        lat_min, lat_max = 39.9, 41.2
        lon_min, lon_max = 15.2, 17.2

        lat_key = 'latitude' if 'latitude' in ds.coords else 'lat'
        lon_key = 'longitude' if 'longitude' in ds.coords else 'lon'

        # Slice geografico per risparmiare RAM su GitHub Actions
        ds_cropped = ds.sel({
            lat_key: slice(lat_max, lat_min), 
            lon_key: slice(lon_min, lon_max)
        })

        df = ds_cropped[var_name].to_dataframe().reset_index()
        # Filtro pioggia (SRI > 0.2 mm/h)
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
            "source_file": filename,
            "points": radar_points
        }

        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        print(f"✅ Successo! Generati {len(radar_points)} punti radar.")

    except Exception as e:
        print(f"❌ Errore analisi: {e}")
    finally:
        # Pulizia
        for f in ["temp_radar.grib", "temp_radar.grib.923a8.idx"]:
            if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    process()
