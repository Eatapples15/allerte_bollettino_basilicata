import pygrib
import json
import requests
import os
from datetime import datetime

# URL del dataset MeteoHub per il Radar DPC
RADAR_URL = "https://meteohub.agenziaitaliameteo.it/api/v1/datasets/radar_dpc/latest"

def main():
    print("🛰️ Download dati Radar DPC...")
    # 1. Download del file Grib
    response = requests.get(RADAR_URL)
    with open("radar_latest.grib", "wb") as f:
        f.write(response.content)

    # 2. Parsing del file GRIB
    grbs = pygrib.open("radar_latest.grib")
    grb = grbs.select(name='Surface rainfall intensity')[0]
    data, lats, lons = grb.data(lat1=39.5, lat2=41.5, lon1=15.2, lon2=17.0) # Ritaglio sulla Basilicata

    # 3. Conversione in formato leggero per la mappa
    radar_points = []
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = float(data[i, j])
            if val > 0.2: # Filtro rumore/pioggia assente
                radar_points.append([float(lats[i,j]), float(lons[i,j]), val])

    radar_output = {
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "points": radar_points
    }

    with open("radar_data.json", "w") as f:
        json.dump(radar_output, f)
    
    print(f"✅ Radar processato: {len(radar_points)} punti rilevati.")

if __name__ == "__main__":
    main()
