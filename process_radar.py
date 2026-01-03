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

# CONFIGURAZIONE METEOHUB
DATASET_ID = "radar_dpc"
LIST_URL = f"https://meteohub.agenziaitaliameteo.it/api/datasets/{DATASET_ID}/opendata"
DOWNLOAD_BASE = "https://meteohub.agenziaitaliameteo.it/api/opendata"
OUTPUT_FILE = "radar_data.json"

def get_latest_opendata_filename():
    """Interroga l'elenco opendata e gestisce la risposta complessa (lista di dizionari)"""
    try:
        print(f"🔍 Recupero elenco file opendata per {DATASET_ID}...")
        r = requests.get(LIST_URL, timeout=30)
        if r.status_code == 200:
            files_data = r.json() 
            
            if not files_data or not isinstance(files_data, list):
                print("⚠️ Risposta API vuota o formato non valido.")
                return None

            # MeteoHub restituisce dizionari: [{"name": "...", "created": "..."}, ...]
            # Ordiniamo per la chiave 'name' o 'created' se disponibile
            try:
                # Proviamo a ordinare per nome del file che contiene il timestamp
                # Assumiamo che la chiave sia 'name' come da standard Mistral
                files_data.sort(key=lambda x: x.get('name', ''), reverse=True)
                latest_entry = files_data[0]
                latest_filename = latest_entry.get('name')
                
                if latest_filename:
                    print(f"✅ Ultimo file rilevato: {latest_filename}")
                    return latest_filename
            except Exception as sort_err:
                print(f"⚠️ Errore durante l'ordinamento dei file: {sort_err}")
                
    except Exception as e:
        print(f"⚠️ Errore ricerca file: {e}")
    return None

def download_file(filename):
    url = f"{DOWNLOAD_BASE}/{filename}"
    print(f"📥 Download in corso: {url}")
    try:
        # User-agent necessario per evitare blocchi
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, timeout=120, stream=True, headers=headers)
        if r.status_code == 200:
            with open("temp_radar.grib", "wb") as f:
                f.write(r.content)
            size = os.path.getsize("temp_radar.grib")
            print(f"📦 Download completato ({size} bytes)")
            return size > 10000
        else:
            print(f"❌ Errore HTTP: {r.status_code}")
    except Exception as e:
        print(f"❌ Errore download: {e}")
    return False

def process():
    filename = get_latest_opendata_filename()
    
    if not filename:
        print("❌ Nessun file trovato nell'elenco opendata.")
        return

    if not download_file(filename):
        print("❌ Impossibile scaricare il file selezionato.")
        return

    try:
        print("⚙️ Analisi GRIB con xarray...")
        ds = xr.open_dataset("temp_radar.grib", engine="cfgrib", backend_kwargs={'indexpath': ''})
        
        var_name = list(ds.data_vars)[0]
        print(f"📊 Analisi variabile: {var_name}")

        # Area Basilicata
        lat_min, lat_max = 39.9, 41.2
        lon_min, lon_max = 15.2, 17.2

        lat_key = 'latitude' if 'latitude' in ds.coords else 'lat'
        lon_key = 'longitude' if 'longitude' in ds.coords else 'lon'

        # Slice geografico per risparmiare RAM
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
            "count": len(radar_points),
            "points": radar_points
        }

        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        print(f"✅ Successo! Generati {len(radar_points)} punti radar.")

    except Exception as e:
        print(f"❌ Errore analisi: {e}")
    finally:
        for f in ["temp_radar.grib", "temp_radar.grib.923a8.idx"]:
            if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    process()
