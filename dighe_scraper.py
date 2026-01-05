import requests
from bs4 import BeautifulSoup
import pdfplumber
import io
import json
import os
from datetime import datetime

def clean_numeric(value):
    """Converte stringhe come '480.700.000' o '252,00' in float."""
    if not value or value.strip() in ["----------", "", None]:
        return 0.0
    try:
        # Rimuove i punti delle migliaia e cambia la virgola decimale in punto
        cleaned = value.replace('.', '').replace(',', '.').replace('*', '').strip()
        return float(cleaned)
    except ValueError:
        return 0.0

def get_current_month_url():
    mesi = {
        1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile",
        5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto",
        9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"
    }
    ora = datetime.now()
    return f"https://acquedelsudspa.it/servizi/{mesi[ora.month]}-{ora.year}/"

def scrape_bollettino():
    url_pagina = get_current_month_url()
    headers = {'User-Agent': 'Mozilla/5.0'}
    file_json = "storico_invasi.json"
    
    try:
        response = requests.get(url_pagina, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if 'Bollettino' in a['href'] and '.pdf' in a['href']]
        
        if not links:
            return print("Nessun bollettino trovato.")

        ultimo_pdf_url = links[-1]
        data_bollettino = ultimo_pdf_url.split('_')[-1].replace('.pdf', '')
        
        pdf_res = requests.get(ultimo_pdf_url, headers=headers)
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            table = pdf.pages[0].extract_table()
            if not table: return

            nuovi_dati = []
            # Saltiamo le prime righe di intestazione del PDF
            for row in table[3:]: 
                if not row[0] or "DESCRIZIONE" in row[0]: continue
                
                nome_diga = row[0].split('\n')[0].strip() # Prende solo il nome principale
                quota_max = clean_numeric(row[1])
                lordo_attuale = clean_numeric(row[8]) # Colonna lordo mc odierno
                capacita_max_lorda = clean_numeric(row[2])

                # Calcolo percentuale di riempimento rispetto alla capacità massima lorda
                percentuale = round((lordo_attuale / capacita_max_lorda * 100), 2) if capacita_max_lorda > 0 else 0

                nuovi_dati.append({
                    "diga": nome_diga,
                    "quota_max_regolazione": quota_max,
                    "capacita_max_lorda_mc": capacita_max_lorda,
                    "volume_lordo_attuale_mc": lordo_attuale,
                    "percentuale_riempimento": percentuale,
                    "pioggia_mm": clean_numeric(row[10]),
                    "data_bollettino": data_bollettino
                })

            # Gestione File JSON
            storico = {}
            if os.path.exists(file_json):
                with open(file_json, 'r', encoding='utf-8') as f:
                    storico = json.load(f)
            
            # Usiamo la data come chiave per evitare duplicati
            storico[data_bollettino] = {
                "scraped_at": datetime.now().isoformat(),
                "dati": nuovi_dati
            }

            with open(file_json, 'w', encoding='utf-8') as f:
                json.dump(storico, f, indent=4, ensure_ascii=False)
            
            print(f"Aggiornato JSON con i dati del {data_bollettino}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape_bollettino()
