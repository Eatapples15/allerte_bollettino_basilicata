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

# CONFIGURAZIONE API MISTRAL/METEO-HUB
# Usiamo l'endpoint di ricerca per trovare l'ultimo run disponibile
SEARCH_URL = "https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/search"
OUTPUT_FILE = "radar_data.json"

def get_latest_radar_url():
    """Interroga l'indice di Meteo-Hub per trovare l'URL del file più recente"""
    try:
        print("🔍 Ricerca ultimo dataset radar disponibile...")
        # Cerchiamo gli ultimi dataset caricati
        r = requests.get(SEARCH_URL, params={"limit": 1}, timeout=30)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                # Estraiamo l'ID dell'ultimo file
                latest_id = data[0]['id']
                download_url = f"https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/{latest_id}/download"
                print(f"✅ Trovato dataset: {latest_id}")
                return download_url
    except Exception as e:
        print(f"⚠️ Errore durante la ricerca: {e}")
    
    # Fallback all'URL generico se la ricerca fallisce
    return "https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/latest"

def download_radar(url):
    print(f"📥 Download in corso da: {url}")
    try:
        r = requests.get(url, timeout=120, stream=True)
        if r.status_code == 200:
            with open("temp_radar.grib", "wb") as f:
                f.write(r.content)
            if os.path.getsize("temp_radar.grib") > 10000:
                print(f"✅ File scaricato ({os.path.getsize('temp_radar.grib')} bytes)")
                return True
        print(f"⚠️ Errore download: Status {r.status_code}")
    except Exception as e:
        print(f"❌ Eccezione download: {e}")
    return False

def process():
    # 1. Trova l'URL dinamico
    target_url = get_latest_radar_url()
    
    # 2. Scarica (con un piccolo retry)
    success = False
    for attempt in range(2):
        if download_radar(target_url):
            success = True
            break
        print("Riprovo tra 10 secondi...")
        time.sleep(10)
    
    if not success:
        print("❌ Impossibile ottenere dati validi. Esco.")
        return

    # 3. Elaborazione scientifica (Ritaglio per RAM)
    try:
        print("⚙️ Analisi GRIB con xarray...")
        ds = xr.open_dataset("temp_radar.grib", engine="cfgrib", backend_kwargs={'indexpath': ''})
        
        var_name = list(ds.data_vars)[0]
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
        # Filtro pioggia significativa (> 0.2 mm/h)
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

        print(f"✅ Successo! Generati {len(radar_points)} punti radar.")

    except Exception as e:
        print(f"❌ Errore elaborazione: {e}")
        # Struttura minima per evitare crash della mappa
        if not os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "w") as f:
                json.dump({"last_update": "N/D", "points": []}, f)
    
    finally:
        # Pulizia
        for tmp in ["temp_radar.grib", "temp_radar.grib.923a8.idx"]:
            if os.path.exists(tmp): os.remove(tmp)

if __name__ == "__main__":
    process()
