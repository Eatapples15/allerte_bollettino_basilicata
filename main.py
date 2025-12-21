import requests
import pdfplumber
import json
import os
import datetime
import re
import sys
import urllib.parse
from bs4 import BeautifulSoup

# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ONESIGNAL_APP_ID = os.environ.get("ONESIGNAL_APP_ID")
ONESIGNAL_API_KEY = os.environ.get("ONESIGNAL_API_KEY")

BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/"
LIST_URL = "https://centrofunzionale.regione.basilicata.it/it/bollettini-avvisi.php?lt=A"
PDF_FILENAME = "bollettino.pdf"
JSON_FILENAME = "dati_bollettino.json"

FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

def send_push_notification(title, message):
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY: return "OneSignal non configurato"
    header = {"Content-Type": "application/json; charset=utf-8", "Authorization": f"Basic {ONESIGNAL_API_KEY}"}
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["Total Subscriptions"],
        "headings": {"en": title, "it": title},
        "contents": {"en": message, "it": message},
        "url": "https://www.formazionesicurezza.org/protezionecivile/bollettino/index.html"
    }
    try: requests.post("https://onesignal.com/api/v1/notifications", headers=header, data=json.dumps(payload))
    except: pass
    return "OK"

def send_telegram_message(message, file_path=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return "Telegram non configurato"
    url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        requests.post(url_msg, data=data)
        if file_path and os.path.exists(file_path):
            url_doc = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
            with open(file_path, 'rb') as f: requests.post(url_doc, data={"chat_id": TELEGRAM_CHAT_ID}, files={'document': f})
    except: pass
    return "OK"

# --- LOGICA INTELLIGENTE COLORI E RISCHI ---
def analizza_riga(celle):
    """
    Analizza le 3 colonne di rischio (Idrogeologica, Temporali, Idraulica).
    Restituisce: (colore_finale, descrizione_rischio)
    Priorità: ROSSO > ARANCIONE > GIALLO > VERDE
    """
    # Indici colonne nel PDF (spesso sono: 1=Idro, 2=Temporali, 3=Idraulica)
    # Se la lista è pulita: [Zona, Idro, Temp, Idraulica, Note]
    
    livelli = {"VERDE": 0, "GIALL": 1, "ARANC": 2, "ROSS": 3}
    colori_output = {0: "green", 1: "yellow", 2: "orange", 3: "red"}
    
    max_score = 0
    descrizione = "Nessuna criticità rilevante"
    
    # Mappatura colonne (dipende da come pdfplumber estrae, assumiamo ordine standard)
    labels = ["Rischio Idrogeologico", "Rischio Temporali", "Rischio Idraulico"]
    
    # Controlliamo le celle dalla 1 alla 3 (la 0 è la Zona)
    for i in range(1, len(celle)):
        if i > 3: break # Evita note o colonne extra
        
        testo = str(celle[i]).upper()
        punteggio = 0
        if "ROSS" in testo: punteggio = 3
        elif "ARANC" in testo: punteggio = 2
        elif "GIALL" in testo: punteggio = 1
        
        if punteggio > 0:
            # Se troviamo un rischio, aggiorniamo descrizione
            tipo_rischio = labels[i-1] if (i-1) < len(labels) else "Criticità"
            
            if punteggio > max_score:
                max_score = punteggio
                descrizione = f"{tipo_rischio}" # Sovrascrive col rischio più grave
            elif punteggio == max_score:
                descrizione += f" + {tipo_rischio}" # Aggiunge se pari merito
                
    if max_score == 0:
        descrizione = "Nessuna criticità ordinaria"

    return colori_output[max_score], descrizione

def get_pdf_url():
    try:
        r = requests.get(LIST_URL, headers=FAKE_HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                return BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
    except: pass
    return None

def main():
    force = os.environ.get("FORCE_SEND") == "true"
    pdf_url = get_pdf_url()
    if not pdf_url: return

    try:
        r = requests.get(pdf_url, headers=FAKE_HEADERS)
        with open(PDF_FILENAME, 'wb') as f: f.write(r.content)
    except: return

    pdf_date = datetime.date.today().strftime("%d/%m/%Y")
    
    extracted = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "data_bollettino": pdf_date,
        "validita_inizio": "N/D", "validita_fine": "N/D",
        "zone": {},
        "dettagli_rischi": {} # NUOVO CAMPO PER MAPPA
    }

    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            text = pdf.pages[0].extract_text()
            d_match = re.search(r"DEL (\d{2}/\d{2}/\d{4})", text)
            if d_match: extracted["data_bollettino"] = d_match.group(1)
            
            # Date validità
            v_start = re.search(r"Inizio validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
            v_end = re.search(r"Fine validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
            if v_start: extracted["validita_inizio"] = v_start.group(1).strip()
            if v_end: extracted["validita_fine"] = v_end.group(1).strip()

            # Estrazione Tabella
            tables = pdf.pages[0].extract_tables()
            if tables:
                for row in tables[0]:
                    cln = [str(c).replace("\n", " ").strip() if c else "" for c in row]
                    if len(cln) >= 4 and "BASI" in cln[0]:
                        zona = cln[0]
                        colore, desc = analizza_riga(cln)
                        extracted["zone"][zona] = colore
                        extracted["dettagli_rischi"][zona] = desc
    except Exception as e: print(e)

    # Verifica se salvare
    if extracted["zone"]:
        # Se non forzato e data uguale, stop. Ma se forzato sovrascrivi.
        with open(JSON_FILENAME, 'w') as f: json.dump(extracted, f, indent=4)
        
        # Notifiche
        msg = f"🚨 *Bollettino {extracted['data_bollettino']}*\nValidità: {extracted['validita_inizio']}\n\n"
        for z in sorted(extracted["zone"].keys()):
            c = extracted["zone"][z]
            icon = {"green":"🟢","yellow":"🟡","orange":"🟠","red":"🔴"}.get(c,"⚪")
            dettaglio = extracted["dettagli_rischi"].get(z, "")
            msg += f"{icon} *{z}*: {dettaglio}\n"
        
        msg += "\n📍 [Apri Mappa](https://www.formazionesicurezza.org/protezionecivile/bollettino/mappa.html)"
        
        send_telegram_message(msg, PDF_FILENAME)
        send_push_notification(f"Bollettino {extracted['data_bollettino']}", "Dati aggiornati. Controlla la mappa.")
        print("✅ Aggiornamento completato.")

if __name__ == "__main__":
    main()
