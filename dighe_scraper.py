import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import sys

def scrape():
    # Recupera l'API Key dai segreti di GitHub
    api_key = os.getenv('SCRAPERAPI_KEY')
    if not api_key:
        print("Errore: SCRAPERAPI_KEY non trovata.")
        sys.exit(1)

    target_url = "http://www.adb.basilicata.it/adb/risorseidriche/dispoidriche/sceglidatidighe.asp"
    
    # Configurazione ScraperAPI per usare IP Italiani
    params = {
        'api_key': api_key,
        'url': target_url,
        'country_code': 'it',  # <--- Forza l'IP italiano
        'keep_headers': 'true',
        'device_type': 'desktop'
    }

    # Il sito richiede un POST per mostrare i dati
    payload = {'listadighe': '0', 'Submit': 'Visualizza'}

    try:
        print("Connessione tramite ScraperAPI con IP Italiano...")
        # Passiamo i parametri di ScraperAPI nell'URL e il payload nel corpo della POST
        response = requests.post('http://api.scraperapi.com', params=params, data=payload, timeout=60)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'border': '1'}) 
        
        if not table:
            # Debug: se non trova la tabella, stampa parte dell'HTML ricevuto
            print("Tabella non trovata. HTML ricevuto:")
            print(response.text[:500])
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

    except Exception as e:
        print(f"Errore durante lo scraping: {e}")
        sys.exit(1)

if __name__ == "__main__":
    scrape()
