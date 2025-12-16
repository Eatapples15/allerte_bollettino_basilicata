import requests
import pdfplumber
import json
import os
import datetime
import re
import sys

# --- CONFIGURAZIONE ---
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/"
LIST_URL = "https://centrofunzionale.regione.basilicata.it/it/bollettini-avvisi.php?lt=A"
PDF_FILENAME = "bollettino.pdf"
JSON_FILENAME = "dati_bollettino.json"

# Telegram Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message, file_path=None):
    """Invia messaggio ed eventuale PDF a Telegram con LOG DI DEBUG COMPLETO"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERRORE CRITICO: Telegram Token o Chat ID mancanti nelle Variabili d'Ambiente.")
        return

    # 1. Invio Testo (Senza Markdown per evitare errori di formattazione in fase di test)
    url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
        # "parse_mode": "Markdown" # DISABILITATO TEMPORANEAMENTE PER DEBUG
    }

    print(f"--- INIZIO INVIO TELEGRAM ---")
    print(f"Target Chat ID: {TELEGRAM_CHAT_ID}")
    
    try:
        resp = requests.post(url_msg, data=data)
        print(f"Esito Invio Testo (Status): {resp.status_code}")
        print(f"Risposta API Telegram (Body): {resp.text}")
    except Exception as e:
        print(f"Errore connessione Telegram (Testo): {e}")

    # 2. Invio PDF
    if file_path and os.path.exists(file_path):
        print("Tentativo invio PDF...")
        url_doc = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        try:
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data_doc = {"chat_id": TELEGRAM_CHAT_ID}
                resp_doc = requests.post(url_doc, data=data_doc, files=files)
                print(f"Esito Invio PDF (Status): {resp_doc.status_code}")
                # Non stampiamo tutto il body del PDF per pulizia, solo status
                if resp_doc.status_code != 200:
                    print(f"Errore risposta PDF: {resp_doc.text}")
        except Exception as e:
            print(f"Errore connessione Telegram (PDF): {e}")
    
    print(f"--- FINE INVIO TELEGRAM ---")

def parse_alert_color(text):
    text = str(text).upper()
    if "ROSS" in text: return "red"
    if "ARANCIONE" in text: return "orange"
    if "GIALL" in text: return "yellow"
    if "VERDE" in text: return "green"
    return "green"

def get_pdf_url():
    try:
        r = requests.get(LIST_URL)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                return BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
    except Exception as e:
        print(f"Errore scraping URL: {e}")
    return None

def main():
    print("Avvio script...")
    
    # 1. Trova l'URL
    pdf_url = get_pdf_url()
    if not pdf_url:
        print("ERRORE: Nessun URL bollettino trovato.")
        return

    print(f"URL Trovato: {pdf_url}")

    # 2. Scarica il PDF
    try:
        r = requests.get(pdf_url)
        with open(PDF_FILENAME, 'wb') as f:
            f.write(r.content)
        print("PDF Scaricato correttamente.")
    except Exception as e:
        print(f"Errore download PDF: {e}")
        return

    # 3. Estrai la data
    bollettino_date = ""
    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            match = re.search(r'\d{2}/\d{2}/\d{4}', first_page_text)
            if match:
                bollettino_date = match.group(0)
    except Exception as e:
        print(f"Errore lettura PDF (pdfplumber): {e}")

    if not bollettino_date:
        bollettino_date = str(datetime.date.today())
        print(f"Data non trovata nel PDF, uso data odierna: {bollettino_date}")
    else:
        print(f"Data estratta dal PDF: {bollettino_date}")

    # 4. Controllo duplicati (DISABILITATO PER DEBUG)
    if os.path.exists(JSON_FILENAME):
        try:
            with open(JSON_FILENAME, 'r') as f:
                old_data = json.load(f)
                if old_data.get("data_bollettino") == bollettino_date:
                    print(f"AVVISO: Bollettino del {bollettino_date} già presente nel JSON.")
                    print("DEBUG MODE ATTIVO: Continuo comunque l'esecuzione per testare Telegram.")
        except Exception as e:
            print(f"Errore lettura JSON precedente: {e}")
    
    # 5. Parsing Dati
    print("Elaborazione dati...")
    extracted_data = {"data_bollettino": bollettino_date, "zone": []}
    
    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            tables = pdf.pages[0].extract_tables()
            if tables:
                table = tables[0]
                for row in table[1:]:
                    if row[0] and "BASI" in str(row[0]):
                        zone_name = row[0].replace("\n", " ").strip()
                        color_text = row[1] if len(row) > 1 else "Verde"
                        color = parse_alert_color(color_text)
                        extracted_data["zone"].append({"nome": zone_name, "colore": color})
            else:
                print("ATTENZIONE: Nessuna tabella trovata a pagina 1.")
    except Exception as e:
        print(f"Errore durante il parsing della tabella: {e}")

    # 6. Salva JSON
    with open(JSON_FILENAME, 'w') as f:
        json.dump(extracted_data, f, indent=4)
    print("File JSON aggiornato.")

    # 7. Invia a Telegram
    msg_text = f"🚨 Nuovo Bollettino Protezione Civile\nData: {bollettino_date}\n\n"
    
    if not extracted_data["zone"]:
        msg_text += "⚠️ Attenzione: Impossibile leggere i dati delle zone dal PDF. Controllare il file allegato.\n"
    else:
        for zona in extracted_data["zone"]:
            icon = "🟢" if zona['colore'] == "green" else "🟡" if zona['colore'] == "yellow" else "🟠" if zona['colore'] == "orange" else "🔴"
            msg_text += f"{icon} {zona['nome']}: {zona['colore'].upper()}\n"
    
    msg_text += "\nScarica il bollettino allegato per i dettagli."
    
    send_telegram_message(msg_text, PDF_FILENAME)

if __name__ == "__main__":
    main()
