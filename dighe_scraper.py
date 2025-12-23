import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os

def scrape():
    url = "http://www.adb.basilicata.it/adb/risorseidriche/dispoidriche/sceglidatidighe.asp"
    
    # Parametri per simulare la scelta "Tutte le dighe" e l'invio del form
    # Questi nomi di campi derivano dall'analisi dell'HTML del sito
    payload = {
        'listadighe': '0', # '0' solitamente corrisponde a "Tutte"
        'Submit': 'Visualizza'
    }

    try:
        response = requests.post(url, data=payload, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'border': '1'}) # Cerca la tabella dei dati
        
        if not table:
            print("Tabella non trovata")
            return

        rows = table.find_all('tr')
        data = []
        for row in rows:
            cols = [ele.text.strip() for ele in row.find_all(['td', 'th'])]
            if cols:
                data.append(cols)

        # Creazione DataFrame
        df = pd.DataFrame(data)
        
        # Aggiungiamo una colonna con la data di esecuzione dello scraping
        df['Data_Scraping'] = datetime.now().strftime("%Y-%m-%d")

        # Salva il file (append se esiste già, o crea nuovo)
        file_name = "storico_invasi.csv"
        if not os.path.isfile(file_name):
            df.to_csv(file_name, index=False, header=False)
        else:
            df.to_csv(file_name, mode='a', index=False, header=False)
            
        print(f"Dati salvati con successo in {file_name}")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape()
