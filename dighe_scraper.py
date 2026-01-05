import requests
from bs4 import BeautifulSoup
import pdfplumber
import io
import json
import os
import re
from datetime import datetime

# --- CONFIGURAZIONE ---
FILE_JSON = "storico_invasi.json"

def clean_numeric(value):
    """
    Pulisce i dati numerici dai PDF. 
    Gestisce asterischi, spazi, punti delle migliaia e virgole decimali.
    """
    if value is None:
        return 0.0
    # Rimuove tutto ciò che non è numero, virgola, punto o meno
    cleaned = str(value).replace(' ', '').replace('----------', '0')
    cleaned = re.sub(r'[^\d,.-]', '', cleaned)
    
    if not cleaned:
        return 0.0
    
    try:
        # Formato IT: 1.234.567,89 -> Formato EN: 1234567.89
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        print(f"Verifica pagina: {url_pagina}")
        response = requests.get(url_pagina, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if 'Bollettino' in a['href'] and '.pdf' in a['href']]
        
        if not links:
            print("Nessun link PDF trovato.")
            return

        ultimo_pdf_url = links[-1]
        # Estrazione data dall'URL (es: Bollettino_05-gennaio-2026.pdf)
        data_match = re.search(r'(\d{2}-\w+-\d{4})', ultimo_pdf_url)
        data_bollettino = data_match.group(1) if data_match else datetime.now().strftime("%d-%m-%Y")
        
        print(f"Scarico PDF: {ultimo_pdf_url}")
        pdf_res = requests.get(ultimo_pdf_url, headers=headers)
        
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            # Estrattore tabella con tolleranza per le linee spezzate (tipico del Camastra)
            table_settings = {
                "vertical_strategy": "text", 
                "horizontal_strategy": "text",
                "snap_tolerance": 4,
            }
            
            page = pdf.pages[0]
            table = page.extract_table(table_settings)
            
            if not table:
                print("Tabella non rilevata.")
                return

            nuovi_dati = []
            for row in table:
                # Salta intestazioni o righe vuote
                if not row or not row[0] or any(x in row[0].upper() for x in ["DIGA", "DESCRIZIONE", "INVASI"]):
                    continue
                
                # Pulizia nome diga (rimuove note e a capo)
                nome_diga = row[0].split('\n')[0].strip()
                
                # Estrazione volumi: 
                # Colonna 2: Capacità Max Lorda
                # Colonna 8 o 9: Volume Lordo Attuale (dipende dalla spaziatura del PDF)
                cap_max = clean_numeric(row[2])
                
                # Logica Camastra/Robustezza: controlla colonne adiacenti se trovi 0
                vol_lordo = clean_numeric(row[8])
                if vol_lordo == 0 and len(row) > 9:
                    vol_lordo = clean_numeric(row[9])
                
                # Calcolo percentuale
                percentuale = round((vol_lordo / cap_max * 100), 2) if cap_max > 0 else 0

                nuovi_dati.append({
                    "diga": nome_diga,
                    "capacita_max_lorda_mc": cap_max,
                    "volume_lordo_attuale_mc": vol_lordo,
                    "percentuale_riempimento": percentuale,
                    "data_bollettino": data_bollettino
                })

            # Gestione Storico JSON
            storico = {}
            if os.path.exists(FILE_JSON):
                with open(FILE_JSON, 'r', encoding='utf-8') as f:
                    try:
                        storico = json.load(f)
                    except json.JSONDecodeError:
                        storico = {}
            
            # Aggiorna o aggiungi la data
            storico[data_bollettino] = {
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "dati": nuovi_dati
            }

            with open(FILE_JSON, 'w', encoding='utf-8') as f:
                json.dump(storico, f, indent=4, ensure_ascii=False)
            
            print(f"Salvataggio completato per il bollettino del {data_bollettino}")

    except Exception as e:
        print(f"Errore durante lo scraping: {e}")

if __name__ == "__main__":
    scrape_bollettino()
