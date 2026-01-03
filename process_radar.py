import requests
import json
import os
import time
from datetime import datetime, timedelta

# Import scientifici
try:
    import xarray as xr
    import pandas as pd
    import cfgrib
except ImportError as e:
    print(f"❌ Librerie scientifiche mancanti: {e}")
    exit(1)

# CONFIGURAZIONE
SEARCH_URL = "https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/search"
OUTPUT_FILE = "radar_data.json"

def get_latest_radar_url():
    """Interroga Meteo-Hub cercando dataset validi nell'ultima ora"""
    try:
        print("🔍 Ricerca ultimo dataset radar disponibile...")
        
        # Cerchiamo dataset prodotti nelle ultime 2 ore per essere sicuri
        time_limit = (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        params = {
            "limit": 5,
            "sort": "-created", # Dal più recente
            "status": "COMPLETED" # Solo file pronti
        }
        
        r = requests.get(SEARCH_URL, params=params, timeout=30)
        
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                # Prendiamo il primo ID valido
                latest_id = data[0]['id']
                download_url = f"https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/{latest_id}/download"
                print(f"✅ Trovato dataset valido: {latest_id} (creato il {data[0].get('created')})")
                return download_url
            else:
                print("⚠️ Nessun dataset trovato con i filtri attuali.")
        else:
            print(f"⚠️ Errore API Search: {r.status_code}")

    except Exception as e:
        print(f"⚠️ Eccezione durante la ricerca: {e}")
    
    # Se tutto fallisce, proviamo il link diretto 'latest' come ultima spiaggia
    print("🔄 Fallback su URL 'latest'...")
    return "https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/latest"

def download_radar(url):
    print(f"📥 Download in corso da: {url}")
    try:
        # Molti server CINECA richiedono headers completi per non dare 404/403
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/octet-stream"
        }
        r = requests.get(url, timeout=120, stream=True, headers=headers)
        
        if r.status_code == 200:
            with open("temp_radar.grib", "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            f_size = os.path.getsize("temp_radar.grib")
            if f_size > 10000:
                print(f"✅ File scaricato con successo ({f_size} bytes)")
                return True
            else:
                print(f"⚠️ File scaricato troppo piccolo ({f_size} bytes), probabilmente vuoto.")
        else:
            print(f"⚠️ Errore download: Status {r.status_code}")
    except Exception as e:
        print(f"❌ Eccezione download: {e}")
    return False

def process():
    # 1. Trova l'URL
    target_url = get_latest_radar_url()
    
    # 2. Scarica
    if not download_radar(target_url):
        # Se il link specifico ha fallito, prova un ultimo tentativo col link generico
        print("尝试 col link generico 'latest'...")
        if not download_radar("https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/latest"):
            print("❌ Impossibile ottenere dati validi dal Radar. Esco.")
            return

    # 3. Elaborazione scientifica
    try:
        print("⚙️ Analisi GRIB con xarray...")
        # L'apertura dei GRIB Radar è lenta, usiamo cache efficace
        ds = xr.open_dataset("temp_radar.grib", engine="cfgrib", backend_kwargs={'indexpath': ''})
        
        var_name = list(ds.data_vars)[0]
        print(f"📊 Variabile: {var_name}")

        # Coordinate Basilicata
        lat_min, lat_max = 39.9, 41.2
        lon_min, lon_max = 15.2, 17.1

        lat_key = 'latitude' if 'latitude' in ds.coords else 'lat'
        lon_key = 'longitude' if 'longitude' in ds.coords else 'lon'

        # Slice geografico prima della conversione (fondamentale per RAM)
        print("✂️ Taglio area regionale...")
        ds_cropped = ds.sel({
            lat_key: slice(lat_max, lat_min), 
            lon_key: slice(lon_min, lon_max)
        })

        df = ds_cropped[var_name].to_dataframe().reset_index()
        
        # Filtro pioggia reale (SRI > 0.2 mm/h)
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

        print(f"✅ Completato! Trovati {len(radar_points)} punti pioggia.")

    except Exception as e:
        print(f"❌ Errore durante l'analisi: {e}")
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"last_update": datetime.now().strftime("%d/%m/%Y %H:%M"), "points": []}, f)
    
    finally:
        # Pulizia file pesanti
        for tmp in ["temp_radar.grib", "temp_radar.grib.923a8.idx"]:
            if os.path.exists(tmp): os.remove(tmp)

if __name__ == "__main__":
    process()
