import requests
import xarray as xr
import json
import os
from datetime import datetime

# Configurazione
GRIB_URL = "https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/latest"
OUTPUT_FILE = "radar_data.json"

def process():
    try:
        print("📥 Download file GRIB dal Radar DPC...")
        r = requests.get(GRIB_URL, timeout=30)
        with open("temp_radar.grib", "wb") as f:
            f.write(r.content)

        # Lettura del file GRIB con cfgrib
        # Il dataset contiene 'sri' (Surface Rainfall Intensity)
        ds = xr.open_dataset("temp_radar.grib", engine="cfgrib")
        
        # Ritaglio (Slicing) sull'area della Basilicata per non caricare dati inutili
        # Nota: le coordinate potrebbero variare in base alla proiezione del GRIB
        basilicata = ds.sel(latitude=slice(41.2, 39.9), longitude=slice(15.3, 16.9))

        radar_points = []
        # Iteriamo sui dati per estrarre solo i punti con pioggia significativa (> 0.2 mm/h)
        df = basilicata.to_dataframe().reset_index()
        
        # Cerchiamo la colonna del valore (solitamente 'sri' o il nome del parametro)
        val_col = [c for c in df.columns if c not in ['latitude', 'longitude', 'time', 'step', 'surface']][0]

        for _, row in df.iterrows():
            if row[val_col] > 0.4: # Filtro per intensità minima (evita rumore)
                radar_points.append({
                    "lat": round(float(row['latitude']), 4),
                    "lon": round(float(row['longitude']), 4),
                    "val": round(float(row[val_col]), 2)
                })

        output = {
            "last_update": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "points": radar_points
        }

        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f)

        print(f"✅ Elaborazione completata. Trovati {len(radar_points)} punti radar.")
        
    except Exception as e:
        print(f"❌ Errore: {e}")
    finally:
        if os.path.exists("temp_radar.grib"):
            os.remove("temp_radar.grib")

if __name__ == "__main__":
    process()
