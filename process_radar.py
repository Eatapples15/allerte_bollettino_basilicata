import requests
import xarray as xr
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime

# URL stabile per l'ultimo run Radar SRI
GRIB_URL = "https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/latest"
OUTPUT_FILE = "radar_data.json"

def process():
    try:
        print("📥 Download file GRIB dal Radar DPC...")
        r = requests.get(GRIB_URL, timeout=120, stream=True)
        
        if r.status_code != 200:
            print(f"❌ Server non raggiungibile: {r.status_code}")
            return

        with open("temp_radar.grib", "wb") as f:
            f.write(r.content)
        
        file_size = os.path.getsize("temp_radar.grib")
        print(f"📦 File scaricato: {file_size} bytes")

        if file_size < 10000:
            print("⚠️ File troppo piccolo, probabilmente non contiene dati validi.")
            return

        print("⚙️ Analisi GRIB con xarray...")
        # Apertura con gestione errori dipendenze
        try:
            ds = xr.open_dataset(
                "temp_radar.grib", 
                engine="cfgrib", 
                backend_kwargs={'indexpath': ''} 
            )
        except Exception as e:
            print(f"❌ Errore apertura engine cfgrib: {e}")
            print("💡 Assicurati di avere 'eccodes' installato sul sistema.")
            return

        # Rilevamento automatico variabili
        var_name = list(ds.data_vars)[0]
        print(f"🔍 Variabile rilevata: {var_name}")

        # Coordinate Basilicata (Leggermente allargate per sicurezza)
        lat_min, lat_max = 39.9, 41.2
        lon_min, lon_max = 15.2, 17.1

        # Conversione in DataFrame
        print("📊 Filtraggio dati in corso...")
        df = ds[var_name].to_dataframe().reset_index()

        # Identificazione colonne lat/lon (possono variare tra latitude/lat o longitude/lon)
        col_lat = 'latitude' if 'latitude' in df.columns else 'lat'
        col_lon = 'longitude' if 'longitude' in df.columns else 'lon'

        # Pulizia dati: rimuoviamo i NaN e applichiamo filtro geografico + intensità
        # Il radar SRI usa valori in mm/h. 0.2 è una pioggerellina leggera.
        df = df.dropna(subset=[var_name])
        
        mask = (df[col_lat] >= lat_min) & (df[col_lat] <= lat_max) & \
               (df[col_lon] >= lon_min) & (df[col_lon] <= lon_max) & \
               (df[var_name] > 0.2)
        
        df_filtered = df[mask]

        radar_points = []
        for _, row in df_filtered.iterrows():
            valore = float(row[var_name])
            # Il DPC a volte codifica valori speciali o molto alti per errori, limitiamo
            if valore > 300: continue 

            radar_points.append({
                "lat": round(float(row[col_lat]), 4),
                "lon": round(float(row[col_lon]), 4),
                "val": round(valore, 2)
            })

        output = {
            "last_update": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "count": len(radar_points),
            "points": radar_points
        }

        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        print(f"✅ Elaborazione completata. Punti rilevati: {len(radar_points)}")
        
    except Exception as e:
        print(f"❌ Errore critico: {e}")
        # Salvataggio file vuoto strutturato per non rompere la mappa
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"last_update": datetime.now().strftime("%d/%m/%Y %H:%M"), "points": []}, f)
    finally:
        if os.path.exists("temp_radar.grib"):
            os.remove("temp_radar.grib")

if __name__ == "__main__":
    process()
