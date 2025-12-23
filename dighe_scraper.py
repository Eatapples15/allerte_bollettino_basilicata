import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os

def scrape():
    url = "http://www.adb.basilicata.it/adb/risorseidriche/dispoidriche/sceglidatidighe.asp"
    payload = {'listadighe': '0', 'Submit': 'Visualizza'}

    try:
        response = requests.post(url, data=payload, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Il sito usa spesso tabelle senza ID, cerchiamo quella con i dati
        table = soup.find('table', {'border': '1'}) 
        
        if not table:
            print("Tabella non trovata")
            return

        data = []
        for row in table.find_all('tr'):
            cols = [ele.text.strip() for ele in row.find_all(['td', 'th'])]
            if cols: data.append(cols)

        df = pd.DataFrame(data)
        df['Data_Esecuzione'] = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Nome file coerente
        file_name = "dati_invasi.csv"
        
        # Se il file non esiste, lo crea con header, altrimenti aggiunge i dati
        if not os.path.isfile(file_name):
            df.to_csv(file_name, index=False)
        else:
            df.to_csv(file_name, mode='a', index=False, header=False)
            
        print(f"Dati salvati in {file_name}")

    except Exception as e:
        print(f"Errore: {e}")
        exit(1) # Forza l'errore se lo scraping fallisce

if __name__ == "__main__":
    scrape()
