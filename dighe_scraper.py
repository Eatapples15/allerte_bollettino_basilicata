import requests
from bs4 import BeautifulSoup
import pdfplumber
import io
import pandas as pd
from datetime import datetime
import os

def get_current_month_url():
    # Mappa mesi in italiano per l'URL
    mesi = {
        1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile",
        5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto",
        9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"
    }
    ora = datetime.now()
    mese_str = mesi[ora.month]
    anno = ora.year
    return f"https://acquedelsudspa.it/servizi/{mese_str}-{anno}/"

def scrape_bollettino():
    url_pagina = get_current_month_url()
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        print(f"Controllo pagina: {url_pagina}")
        response = requests.get(url_pagina, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Trova tutti i link ai PDF dei bollettini
        links = [a['href'] for a in soup.find_all('a', href=True) if 'Bollettino' in a['href'] and '.pdf' in a['href']]
        
        if not links:
            print("Nessun bollettino trovato per il mese corrente.")
            return

        # Prende l'ultimo link (il più recente)
        ultimo_pdf_url = links[-1]
        data_bollettino = ultimo_pdf_url.split('_')[-1].replace('.pdf', '')
        print(f"Analisi bollettino del: {data_bollettino}")

        # Scarica il PDF
        pdf_res = requests.get(ultimo_pdf_url, headers=headers)
        
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            # Di solito i dati sono nella prima pagina
            table = pdf.pages[0].extract_table()
            
            if not table:
                print("Impossibile estrarre la tabella dal PDF.")
                return

            # Pulizia dati: creiamo il DataFrame
            # Nota: le tabelle nei PDF possono avere righe vuote o intestazioni sporche
            df_temp = pd.DataFrame(table)
            
            # Aggiungiamo metadati
            df_temp['data_bollettino'] = data_bollettino
            df_temp['data_aggiornamento'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            file_name = "storico_invasi_basilicata.csv"
            
            # Salvataggio (Append)
            if not os.path.exists(file_name):
                df_temp.to_csv(file_name, index=False)
            else:
                # Carichiamo l'esistente per evitare duplicati della stessa data
                df_esistente = pd.read_csv(file_name)
                if data_bollettino not in df_esistente['data_bollettino'].values:
                    df_temp.to_csv(file_name, mode='a', index=False, header=False)
                    print(f"Dati del {data_bollettino} aggiunti al CSV.")
                else:
                    print(f"Dati del {data_bollettino} già presenti. Salto.")

    except Exception as e:
        print(f"Errore durante lo scraping: {e}")

if __name__ == "__main__":
    scrape_bollettino()
