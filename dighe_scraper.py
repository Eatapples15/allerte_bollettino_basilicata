import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import time

def scrape():
    url = "http://www.adb.basilicata.it/adb/risorseidriche/dispoidriche/sceglidatidighe.asp"
    
    # Simula un browser reale per evitare blocchi
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Origin': 'http://www.adb.basilicata.it',
        'Referer': 'http://www.adb.basilicata.it/adb/risorseidriche/dispoidriche/sceglidatidighe.asp'
    }
    
    payload = {'listadighe': '0', 'Submit': 'Visualizza'}

    # Tentativi multipli (Retry logic)
    for attempt in range(3):
        try:
            print(f"Tentativo {attempt + 1}...")
            response = requests.post(url, data=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Se arriviamo qui, la connessione è riuscita
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', {'border': '1'}) 
            
            if not table:
                print("Connesso, ma tabella non trovata.")
                return

            data = []
            for row in table.find_all('tr'):
                cols = [ele.text.strip() for ele in row.find_all(['td', 'th'])]
                if cols: data.append(cols)

            df = pd.DataFrame(data)
            df['Data_Esecuzione'] = datetime.now().strftime("%Y-%m-%d %H:%M")

            file_name = "dati_invasi.csv"
            if not os.path.isfile(file_name):
                df.to_csv(file_name, index=False)
            else:
                df.to_csv(file_name, mode='a', index=False, header=False)
                
            print(f"Successo! Dati salvati in {file_name}")
            return # Esci dalla funzione dopo il successo

        except requests.exceptions.RequestException as e:
            print(f"Errore al tentativo {attempt + 1}: {e}")
            if attempt < 2:
                time.sleep(5) # Aspetta 5 secondi prima di riprovare
            else:
                print("Tutti i tentativi falliti.")
                exit(1)

if __name__ == "__main__":
    scrape()
