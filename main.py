import requests
import pdfplumber
import json
import os
import datetime
import sys

# --- CONFIGURAZIONE ---
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/"
LIST_URL = "https://centrofunzionale.regione.basilicata.it/it/bollettini-avvisi.php?lt=A"
PDF_FILENAME = "bollettino.pdf"
JSON_FILENAME = "dati_bollettino.json"

# Telegram Secrets (impostati su GitHub)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message, file_path=None):
    """Invia messaggio ed eventuale PDF a Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram Token o Chat ID mancanti.")
        return

    # Invio Testo
    url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url_msg, data=data)

    # Invio PDF
    if file_path:
        url_doc = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data_doc = {"chat_id": TELEGRAM_CHAT_ID}
            requests.post(url_doc, data=data_doc, files=files)

def parse_alert_color(text):
    text = text.upper()
    if "ROSS" in text: return "red"
    if "ARANCIONE" in text: return "orange"
    if "GIALL" in text: return "yellow"
    if "VERDE" in text: return "green"
    return "green"

def get_pdf_url():
    try:
        r = requests.get(LIST_URL)
        # Logica semplificata per trovare il link (da adattare se il sito è complesso)
        # Cerca href che contiene "Bollettino_Criticita"
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                return BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
    except Exception as e:
        print(e)
    return None

def main():
    # 1. Trova l'URL del bollettino
    pdf_url = get_pdf_url()
    if not pdf_url:
        print("Nessun URL trovato.")
        return

    print(f"URL Trovato: {pdf_url}")

    # 2. Scarica il PDF
    r = requests.get(pdf_url)
    with open(PDF_FILENAME, 'wb') as f:
        f.write(r.content)

    # 3. Estrai la data dal PDF (o usa l'URL come ID univoco)
    # Per semplicità, qui estraiamo la data dal testo
    bollettino_date = ""
    with pdfplumber.open(PDF_FILENAME) as pdf:
        first_page_text = pdf.pages[0].extract_text()
        # Cerca una stringa tipo "16/12/2025"
        import re
        match = re.search(r'\d{2}/\d{2}/\d{4}', first_page_text)
        if match:
            bollettino_date = match.group(0)
    
    if not bollettino_date:
        bollettino_date = str(datetime.date.today())

    # 4. Confronta con il vecchio JSON per vedere se è nuovo
    is_new = True
    if os.path.exists(JSON_FILENAME):
        with open(JSON_FILENAME, 'r') as f:
            old_data = json.load(f)
            if old_data.get("data_bollettino") == bollettino_date:
                print("Bollettino già processato. Mi fermo.")
                is_new = False
    
    # Se non è nuovo, usciamo (a meno che tu non voglia forzare l'aggiornamento)
    if not is_new:
        return

    # 5. Parsing (Logica semplificata del codice precedente)
    print("Elaborazione nuovo bollettino...")
    extracted_data = {"data_bollettino": bollettino_date, "zone": []}
    
    with pdfplumber.open(PDF_FILENAME) as pdf:
        # Esempio: estrazione tabella pag 1
        table = pdf.pages[0].extract_tables()[0] # Assumiamo sia la prima
        for row in table[1:]:
            if row[0] and "BASI" in row[0]:
                zone_name = row[0].replace("\n", " ").strip()
                color = parse_alert_color(row[1]) # Semplificato: prendiamo idrogeologico
                extracted_data["zone"].append({"nome": zone_name, "colore": color})

    # 6. Salva il JSON
    with open(JSON_FILENAME, 'w') as f:
        json.dump(extracted_data, f, indent=4)

    # 7. Invia a Telegram
    msg_text = f"🚨 *Nuovo Bollettino Protezione Civile*\n📅 Data: {bollettino_date}\n\n"
    for zona in extracted_data["zone"]:
        icon = "🟢" if zona['colore'] == "green" else "🟡" if zona['colore'] == "yellow" else "🟠" if zona['colore'] == "orange" else "🔴"
        msg_text += f"{icon} *{zona['nome']}*: {zona['colore'].upper()}\n"
    
    msg_text += "\nScarica il bollettino completo qui sotto o consulta la mappa."
    
    send_telegram_message(msg_text, PDF_FILENAME)
    print("Notifica inviata e JSON salvato.")

if __name__ == "__main__":
    main()
