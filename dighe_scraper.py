import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os
import sys

def scrape():
    # Recupera la chiave - Assicurati che su GitHub il Secret si chiami SCRAPERAPI_KEY
    api_key = os.getenv('SCRAPERAPI_KEY')
    
    if not api_key:
        print("Errore: La variabile SCRAPERAPI_KEY è vuota o non trovata.")
        sys.exit(1)

    # Endpoint ScraperAPI (usiamo HTTPS)
    proxy_url = 'https://api.scraperapi.com'
    
    # Parametri minimi per evitare conflitti con il piano free
    params = {
        'api_key': api_key,
        'url': 'http://www.adb.basilicata.it/adb/risorseidriche/dispoidriche/sceglidatidighe.asp',
        'country_code': 'it'
    }

    payload = {'listadighe': '0', 'Submit': 'Visualizza'}

    try:
        print(f"Tentativo di connessione per l'URL: {params['url']}")
        # Usiamo una POST tramite ScraperAPI
        response = requests.post(proxy_url, params=params, data=payload, timeout=60)
        
        if response.status_code == 401:
            print("Errore 401: Chiave API non valida o account non attivo. Controlla i Secrets su GitHub.")
            sys.exit(1)
            
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # Il sito dell'AdB usa tabelle con l'attributo border="1" per i dati
        table = soup.find('table', {'border': '1'}) 
        
        if not table:
            print("Tabella non trovata nell'HTML ricevuto.")
            return

        data = []
        for row in table.find_all('tr'):
            cols = [ele.text.strip() for ele in row.find_all(['td', 'th'])]
            if cols and len(cols) > 1: # Evitiamo righe vuote
                data.append(cols)

        df = pd.DataFrame(data)
        df['Data_Scraping'] = datetime.now().strftime("%d/%m/%Y %H:%M")

        file_name = "dati_invasi.csv"
        # Scrittura intelligente: header solo se il file è nuovo
        hdr = not os.path.exists(file_name)
        df.to_csv(file_name, mode='a', index=False, header=hdr, encoding='utf-8')
            
        print(f"Successo! {len(data)} righe scritte in {file_name}")

    except Exception as e:
        print(f"Errore: {e}")
        sys.exit(1)

if __name__ == "__main__":
    scrape()
