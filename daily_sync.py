import requests
import json
import os
from datetime import datetime

RAW_URL = "https://raw.githubusercontent.com/Eatapples15/allerte_bollettino_basilicata/refs/heads/main/dati_bollettino.json"
INDEX_FILE = "data/index.json"

def get_max_severity(zones_dict):
    priority = {"red": 3, "orange": 2, "yellow": 1, "green": 0}
    max_sev = "green"
    for z in zones_dict:
        # Gestisce sia il formato del tuo JSON raw ("oggi") sia quello dello storico
        color = zones_dict[z].get("oggi", "green")
        if priority.get(color, 0) > priority.get(max_sev, 0):
            max_sev = color
    return max_sev

def sync():
    try:
        r = requests.get(RAW_URL)
        new_data = r.json()
        
        date_dt = datetime.strptime(new_data["data_bollettino"], "%d/%m/%Y")
        
        folder = date_dt.strftime("data/%Y/%m")
        os.makedirs(folder, exist_ok=True)
        file_path = f"{folder}/{date_dt.strftime('%d')}.json"
        
        # Salviamo i dati normalizzati
        clean_data = {
            "date": new_data["data_bollettino"],
            "zones": new_data["zone"]
        }
        
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(clean_data, f, indent=2)

        # Calcolo criticità per l'indice
        max_crit = get_max_severity(new_data["zone"])

        # Aggiornamento indice
        if os.path.exists(INDEX_FILE):
            with open(INDEX_FILE, "r", encoding='utf-8') as f:
                index = json.load(f)
        else:
            index = []
        
        new_entry = {
            "d": date_dt.strftime("%Y-%m-%d"), 
            "f": file_path.replace("data/", ""),
            "max_criticality": max_crit
        }
        
        # Evita duplicati
        index = [e for e in index if e["d"] != new_entry["d"]]
        index.append(new_entry)
        index.sort(key=lambda x: x["d"])
        
        with open(INDEX_FILE, "w", encoding='utf-8') as f:
            json.dump(index, f, indent=2)
        
        print(f"Sincronizzazione completata: {new_entry['d']} (Criticità: {max_crit})")
    except Exception as e:
        print(f"Errore durante la sincronizzazione: {e}")

if __name__ == "__main__":
    sync()
