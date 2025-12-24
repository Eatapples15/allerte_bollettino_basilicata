import requests
import xarray as xr
import json
import os
from datetime import datetime

# URL stabile per l'ultimo run Radar SRI (Surface Rainfall Intensity)
GRIB_URL = "https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/latest"
OUTPUT_FILE = "radar_data.json"

def process():
    try:
        print("📥 Download file GRIB dal Radar DPC...")
        r = requests.get(GRIB_URL, timeout=60, stream=True)
        
        # Verifica se il download è andato a buon fine e se è un file reale
        if r.status_code != 200 or len(r.content) < 10000:
            print(f"⚠️ File non disponibile o troppo piccolo ({len(r.content)} bytes). Salto aggiornamento.")
            return

        with open("temp_radar.grib", "wb") as f:
            f.write(r.content)

        print("⚙️ Analisi GRIB in corso...")
        
        # Apertura con indexpath='' per evitare l'errore di creazione file .idx
        ds = xr.open_dataset(
            "temp_radar.grib", 
            engine="cfgrib", 
            backend_kwargs={'indexpath': ''} 
        )

        # Coordinate geografiche approssimative per la Basilicata
        # Nota: Usiamo valori ampi per compensare eventuali rotazioni della griglia
        lat_min, lat_max = 39.9, 41.2
        lon_min, lon_max = 15.2, 17.0

        radar_points = []
        
        # Estraiamo i dati SRI (Rainfall intensity)
        # Il nome della variabile nel GRIB DPC è solitamente 'unknown' o 'sri'
        var_name = list(ds.data_vars)[0]
        data_array = ds[var_name]

        # Trasformazione in DataFrame filtrando subito i valori > 0.4 mm/h
        # Questo riduce drasticamente l'uso della memoria
        df = data_array.to_dataframe().reset_index()
        
        # Filtriamo per area geografica e intensità
        mask = (df['latitude'] >= lat_min) & (df['latitude'] <= lat_max) & \
               (df['longitude'] >= lon_min) & (df['longitude'] <= lon_max) & \
               (df[var_name] > 0.4)
        
        df_filtered = df[mask]

        for _, row in df_filtered.iterrows():
            radar_points.append({
                "lat": round(float(row['latitude']), 4),
                "lon": round(float(row['longitude']), 4),
                "val": round(float(row[var_name]), 2)
            })

        output = {
            "last_update": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "points": radar_points
        }

        with open(OUTPUT_FILE, "w") as f:
            json.dump(output, f)

        print(f"✅ Elaborazione completata. Trovati {len(radar_points)} punti pioggia in Basilicata.")
        
    except Exception as e:
        print(f"❌ Errore durante l'elaborazione: {e}")
        # Crea un file vuoto per evitare l'errore di Git "pathspec did not match"
        if not os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "w") as f:
                json.dump({"last_update": "N/D", "points": []}, f)
    finally:
        if os.path.exists("temp_radar.grib"):
            os.remove("temp_radar.grib")

if __name__ == "__main__":
    process()
