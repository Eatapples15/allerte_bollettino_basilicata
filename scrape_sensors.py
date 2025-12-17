import requests
import json
import datetime
from bs4 import BeautifulSoup
import os

# --- CONFIGURAZIONE ---
# URL ufficiali del Centro Funzionale Basilicata
URL_PIOGGIA = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st=P"
URL_FIUMI = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st=I"
OUTPUT_FILE = "dati_sensori.json"

def clean_value(val_str):
    """Pulisce la stringa del valore (es. '0.2' -> 0.2)"""
    try:
        # Rimuove spazi e caratteri strani
        val_str = val_str.strip()
        if not val_str or val_str == "-" or val_str == "N.D.":
            return None
        return float(val_str)
    except ValueError:
        return None

def scrape_table(url, data_type):
    """Scarica e analizza la tabella HTML"""
    print(f"Scaricamento dati: {data_type}...")
    results = []
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"Errore HTTP {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Cerca tutte le righe delle tabelle
        rows = soup.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            # La struttura solita è: [0]Nome Stazione, [1]Valore, [2]Orario
            if len(cols) >= 3:
                nome = cols[0].text.strip()
                val_raw = cols[1].text.strip()
                orario = cols[2].text.strip()
                
                valore = clean_value(val_raw)
                
                # Accettiamo solo se c'è un valore numerico valido
                if valore is not None:
                    results.append({
                        "stazione": nome,
                        "valore": valore,
                        "ora": orario,
                        "tipo": data_type
                    })
                    
    except Exception as e:
        print(f"Errore durante lo scraping di {data_type}: {e}")
        
    return results

def main():
    print("--- INIZIO AGGIORNAMENTO SENSORI ---")
    
    # 1. Scarica Pioggia
    dati_pioggia = scrape_table(URL_PIOGGIA, "pioggia")
    # Ordina per pioggia decrescente (i valori più alti in cima)
    dati_pioggia.sort(key=lambda x: x["valore"], reverse=True)
    
    # 2. Scarica Fiumi (Idrometri)
    dati_fiumi = scrape_table(URL_FIUMI, "idrometro")
    # Ordina per livello decrescente
    dati_fiumi.sort(key=lambda x: x["valore"], reverse=True)
    
    # 3. Struttura il JSON finale
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "totale_sensori_letti": len(dati_pioggia) + len(dati_fiumi),
        "pioggia": dati_pioggia,
        "fiumi": dati_fiumi
    }
    
    # 4. Salva il file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
        
    print(f"✅ File {OUTPUT_FILE} salvato con successo.")
    print(f"   - Stazioni Pioggia: {len(dati_pioggia)}")
    print(f"   - Stazioni Fiumi: {len(dati_fiumi)}")

if __name__ == "__main__":
    main()
