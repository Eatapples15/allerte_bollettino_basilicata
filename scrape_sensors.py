import requests
import json
import datetime
from bs4 import BeautifulSoup
import os

# --- CONFIGURAZIONE ---
URL_PIOGGIA = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st=P"
URL_FIUMI = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st=I"
OUTPUT_FILE = "dati_sensori.json"

# HEADERS FONDAMENTALI PER EVITARE IL BLOCCO
FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

def clean_value(val_str):
    """Pulisce la stringa del valore (es. '0.2' -> 0.2)"""
    try:
        val_str = val_str.strip()
        if not val_str or val_str == "-" or val_str == "N.D.":
            return None
        # Rimuove unità di misura se presenti
        val_str = val_str.replace("mm", "").replace("m", "").strip()
        return float(val_str)
    except ValueError:
        return None

def scrape_table(url, data_type):
    print(f"Scaricamento dati: {data_type}...")
    results = []
    
    try:
        # Aggiunti headers e timeout
        response = requests.get(url, headers=FAKE_HEADERS, timeout=30)
        if response.status_code != 200:
            print(f"Errore HTTP {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Cerca la tabella (solitamente la prima table nel div main)
        table = soup.find('table')
        if not table: return []

        rows = table.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            # Struttura: [0]Stazione, [1]Valore, [2]Data
            if len(cols) >= 3:
                nome = cols[0].text.strip()
                val_raw = cols[-2].text.strip() # Penultimo è il valore
                orario = cols[-1].text.strip()  # Ultimo è l'orario
                
                valore = clean_value(val_raw)
                
                if valore is not None:
                    # Determina stato per colori frontend
                    stato = "normal"
                    if data_type == "pioggia":
                        if valore > 0: stato = "rain"
                        if valore > 20: stato = "heavy"
                        if valore > 60: stato = "extreme"
                    elif data_type == "idrometro":
                        if valore > 1.5: stato = "alert" # Soglia ipotetica fiumi
                    
                    results.append({
                        "stazione": nome,
                        "valore": valore,
                        "ora": orario,
                        "stato": stato
                    })
                    
    except Exception as e:
        print(f"Errore {data_type}: {e}")
        
    return results

def main():
    print("--- INIZIO AGGIORNAMENTO SENSORI ---")
    
    # 1. Pioggia
    dati_pioggia = scrape_table(URL_PIOGGIA, "pioggia")
    dati_pioggia.sort(key=lambda x: x["valore"], reverse=True) # Ordina per più piovosi
    
    # 2. Fiumi
    dati_fiumi = scrape_table(URL_FIUMI, "idrometro")
    dati_fiumi.sort(key=lambda x: x["valore"], reverse=True) # Ordina per livello più alto
    
    # 3. Output Finale
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "pioggia": dati_pioggia,
        "fiumi": dati_fiumi
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
        
    print(f"✅ Dati salvati: {len(dati_pioggia)} Pluviometri, {len(dati_fiumi)} Idrometri.")

if __name__ == "__main__":
    main()
