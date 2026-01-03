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

        # Apertura dataset
        ds = xr.open_dataset("temp_radar.grib", engine="cfgrib", backend_kwargs={'indexpath': ''})
        
        # Identificazione automatica variabile pioggia
        var_name = list(ds.data_vars)[0]
        print(f"🔍 Variabile rilevata: {var_name}")

        # Conversione in DataFrame e pulizia immediata
        # Usiamo un campionamento (step) se il file è troppo grande per la memoria
        df = ds[var_name].to_dataframe().reset_index()
        
        # Rinominia colonne se necessario (DPC usa spesso latitude/longitude)
        df.rename(columns={'lat': 'latitude', 'lon': 'longitude'}, inplace=True)

        # Filtro Geografico Basilicata
        lat_min, lat_max = 39.9, 41.2
        lon_min, lon_max = 15.2, 17.1
        
        # Filtro: Area Basilicata e pioggia > 0.2 mm/h
        mask = (df['latitude'] >= lat_min) & (df['latitude'] <= lat_max) & \
               (df['longitude'] >= lon_min) & (df['longitude'] <= lon_max) & \
               (df[var_name] > 0.2)
        
        df_filtered = df[mask].dropna()

        radar_points = []
        for _, row in df_filtered.iterrows():
            radar_points.append({
                "lat": round(float(row['latitude']), 3),
                "lon": round(float(row['longitude']), 3),
                "val": round(float(row[var_name]), 2)
            })

        output = {
            "last_update": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "points": radar_points
        }

        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f)

        print(f"✅ Completato! Trovati {len(radar_points)} punti pioggia.")

    except Exception as e:
        print(f"❌ Errore: {e}")
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"last_update": datetime.now().strftime("%d/%m/%Y %H:%M"), "points": []}, f)
    finally:
        if os.path.exists("temp_radar.grib"):
            os.remove("temp_radar.grib")

if __name__ == "__main__":
    process()
