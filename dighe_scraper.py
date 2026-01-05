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
    """Pulisce le stringhe numeriche gestendo spazi, punti e virgole."""
    if value is None:
        return 0.0
    # Rimuove tutto ciò che non è numero, virgola o punto
    cleaned = re.sub(r'[^\d,.-]', '', str(value).replace(' ', ''))
    if not cleaned or cleaned == '-':
        return 0.0
    try:
        # Gestisce il formato italiano: 1.234.567,89 -> 1234567.89
        cleaned = cleaned.replace('.', '').replace(',', '.')
        return float(cleaned)
    except ValueError:
        return 0.0

def scrape_bollettino():
    # ... (logica URL e download PDF identica a prima) ...
    
    with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
        # Proviamo a usare table_settings per essere più precisi con le linee del Camastra
        table_settings = {
            "vertical_strategy": "lines", 
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
        }
        
        page = pdf.pages[0]
        table = page.extract_table(table_settings) or page.extract_table()
        
        if not table:
            print("Impossibile estrarre la tabella.")
            return

        nuovi_dati = []
        for row in table:
            # Filtriamo le righe vuote o di intestazione
            if not row or not row[0] or any(x in row[0].upper() for x in ["DIGA", "DESCRIZIONE", "TOTALE"]):
                continue
            
            nome_diga = row[0].split('\n')[0].strip().upper()
            
            # LOGICA SPECIFICA PER CAMASTRA
            # Spesso il volume attuale è in colonna 8 o 9 a seconda del PDF
            # Cerchiamo il valore più verosimile tra le colonne finali
            try:
                cap_max = clean_numeric(row[2])
                
                # Se la colonna 8 è 0, proviamo la 9 (a volte i dati slittano)
                vol_attuale = clean_numeric(row[8])
                if vol_attuale == 0 and len(row) > 9:
                    vol_attuale = clean_numeric(row[9])
                
                # Ulteriore controllo: se è ancora 0 e non dovrebbe esserlo
                if "CAMASTRA" in nome_diga and vol_attuale == 0:
                    # Debug: stampa la riga per capire dove si trova il dato
                    print(f"DEBUG Camastra Row: {row}")

                percentuale = round((vol_attuale / cap_max * 100), 2) if cap_max > 0 else 0

                nuovi_dati.append({
                    "diga": nome_diga,
                    "capacita_max_lorda_mc": cap_max,
                    "volume_lordo_attuale_mc": vol_attuale,
                    "percentuale_riempimento": percentuale
                })
            except Exception as e:
                print(f"Errore nella riga {nome_diga}: {e}")

        # ... (logica salvataggio JSON identica a prima) ...
