import requests
import pdfplumber
import json
import os
import datetime
import re
import sys

# --- CONFIGURAZIONE DI TEST ---
# Ho inserito direttamente i tuoi dati corretti (senza spazi)
TELEGRAM_TOKEN = "8537876026:AAH8LWBtvzkOm3WmYOf317aN3d1YKNwlAAk" 
TELEGRAM_CHAT_ID = "-1003527149783"

BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/"
LIST_URL = "https://centrofunzionale.regione.basilicata.it/it/bollettini-avvisi.php?lt=A"
PDF_FILENAME = "bollettino.pdf"
JSON_FILENAME = "dati_bollettino.json"

def send_telegram_message(message, file_path=None):
    print(f"--- INIZIO INVIO TELEGRAM ---")
    
    # 1. Invio Testo
    url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    
    try:
        resp = requests.post(url_msg, data=data)
        print(f"Esito Invio Testo: {resp.status_code}")
        # Se c'è errore, stampiamo perché
        if resp.status_code != 200:
            print(f"ERRORE TELEGRAM: {resp.text}")
        else:
            print("MESSAGGIO INVIATO CON SUCCESSO!")
    except Exception as e:
        print(f"Errore connessione: {e}")

    # 2. Invio PDF
    if file_path and os.path.exists(file_path):
        url_doc = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        try:
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data_doc = {"chat_id": TELEGRAM_CHAT_ID}
                resp_doc = requests.post(url_doc, data=data_doc, files=files)
                print(f"Esito Invio PDF: {resp_doc.status_code}")
        except Exception as e:
            print(f"Errore invio PDF: {e}")
            
    print(f"--- FINE INVIO TELEGRAM ---")

def get_pdf_url():
    # Funzione semplificata per il test
    try:
        r = requests.get(LIST_URL)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                return BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
    except:
        pass
    return None

def main():
    print("Avvio TEST DIRETTO...")
    
    # Scarichiamo il PDF per avere qualcosa da inviare
    pdf_url = get_pdf_url()
    if pdf_url:
        print("Scaricamento PDF in corso...")
        r = requests.get(pdf_url)
        with open(PDF_FILENAME, 'wb') as f:
            f.write(r.content)
    else:
        print("Impossibile scaricare PDF, creo un file finto per il test.")
        with open(PDF_FILENAME, 'w') as f:
            f.write("Test file PDF")

    # Proviamo a inviare
    msg = "🚀 TEST DI CONNESSIONE RIUSCITO!\nSe leggi questo messaggio, il bot funziona."
    send_telegram_message(msg, PDF_FILENAME)

if __name__ == "__main__":
    main()
