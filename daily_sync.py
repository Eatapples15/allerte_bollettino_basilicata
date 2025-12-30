import requests
import json
import os
from datetime import datetime

RAW_URL = "https://raw.githubusercontent.com/Eatapples15/allerte_bollettino_basilicata/refs/heads/main/dati_bollettino.json"
INDEX_FILE = "data/index.json"

def sync():
    # 1. Prendi i dati freschi dal tuo scraper giornaliero
    r = requests.get(RAW_URL)
    new_data = r.json()
    
    # Formatta la data (es. da "30/12/2025" a datetime)
    date_dt = datetime.strptime(new_data["data_bollettino"], "%d/%m/%Y")
    
    # 2. Salva il file JSON nella struttura dello storico
    folder = date_dt.strftime("data/%Y/%m")
    os.makedirs(folder, exist_ok=True)
    file_path = f"{folder}/{date_dt.strftime('%d')}.json"
    
    # Salviamo solo la parte "oggi" come lo storico
    clean_data = {
        "date": new_data["data_bollettino"],
        "zones": new_data["zone"]
    }
    
    with open(file_path, "w") as f:
        json.dump(clean_data, f, indent=2)

    # 3. Aggiorna l'index.json
    with open(INDEX_FILE, "r") as f:
        index = json.load(f)
    
    new_entry = {"d": date_dt.strftime("%Y-%m-%d"), "f": file_path.replace("data/", "")}
    
    # Evita duplicati se lanciato più volte
    index = [e for e in index if e["d"] != new_entry["d"]]
    index.append(new_entry)
    index.sort(key=lambda x: x["d"])
    
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)
    
    print(f"Sincronizzazione completata per il giorno: {new_entry['d']}")

if __name__ == "__main__":
    sync()
