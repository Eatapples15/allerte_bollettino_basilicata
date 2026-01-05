import requests
from bs4 import BeautifulSoup
import pdfplumber
import io
import json
import os
import re
from datetime import datetime

FILE_JSON = "storico_invasi.json"

def clean_numeric(value):
    if value is None: return 0.0
    cleaned = str(value).replace(' ', '').replace('----------', '0')
    cleaned = re.sub(r'[^\d,.-]', '', cleaned)
    if not cleaned: return 0.0
    try:
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
        return float(cleaned)
    except ValueError:
        return 0.0

def get_current_month_url():
    mesi = {1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 6: "giugno",
            7: "luglio", 8: "agosto", 9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"}
    ora = datetime.now()
    return f"https://acquedelsudspa.it/servizi/{mesi[ora.month]}-{ora.year}/"

def scrape_bollettino():
    url_pagina = get_current_month_url()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(url_pagina, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if 'Bollettino' in a['href'] and '.pdf' in a['href']]
        
        if not links: return print("Nessun link trovato.")
        
        ultimo_pdf_url = links[-1]
        data_match = re.search(r'(\d{2}-\w+-\d{4})', ultimo_pdf_url)
        data_bollettino = data_match.group(1) if data_match else datetime.now().strftime("%d-%m-%Y")
        
        pdf_res = requests.get(ultimo_pdf_url, headers=headers)
        
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            # Strategia mista per catturare bene le colonne del trend e meteo
            page = pdf.pages[0]
            table = page.extract_table()
            
            if not table: return

            nuovi_dati = []
            for row in table:
                if not row or not row[0] or any(x in row[0].upper() for x in ["DIGA", "DESCRIZIONE", "INVASI"]):
                    continue
                
                nome_diga = row[0].split('\n')[0].strip()
                
                # DATI DI RIFERIMENTO (MAX)
                quota_max_slm = clean_numeric(row[1])
                volume_max_lordo = clean_numeric(row[2])
                
                # DATI ATTUALI (NETTI E TREND)
                quota_attuale_slm = clean_numeric(row[6])
                trend_cm = clean_numeric(row[7]) # Variazione giorno prec.
                volume_attuale_netto = clean_numeric(row[9])
                pioggia_mm = clean_numeric(row[10])
                neve_cm = clean_numeric(row[11])
                
                # Calcolo percentuale di riempimento NETTO rispetto al LORDO MAX
                # (Nota: puoi cambiare volume_max_lordo con un volume netto max se disponibile nel PDF)
                percentuale = round((volume_attuale_netto / volume_max_lordo * 100), 2) if volume_max_lordo > 0 else 0

                nuovi_dati.append({
                    "diga": nome_diga,
                    "quota_max_slm": quota_max_slm,
                    "volume_max_lordo_mc": volume_max_lordo,
                    "quota_attuale_slm": quota_attuale_slm,
                    "volume_netto_attuale_mc": volume_attuale_netto,
                    "percentuale_riempimento": percentuale,
                    "trend_variazione_cm": trend_cm,
                    "pioggia_mm": pioggia_mm,
                    "neve_cm": neve_cm
                })

            storico = {}
            if os.path.exists(FILE_JSON):
                with open(FILE_JSON, 'r', encoding='utf-8') as f:
                    try: storico = json.load(f)
                    except: storico = {}
            
            storico[data_bollettino] = {
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "dati": nuovi_dati
            }

            with open(FILE_JSON, 'w', encoding='utf-8') as f:
                json.dump(storico, f, indent=4, ensure_ascii=False)
            
            print(f"Dati netti e meteo salvati per il {data_bollettino}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape_bollettino()
