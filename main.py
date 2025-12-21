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

# --- PARSING COLORI ---
def get_risk_score(color):
    """Restituisce un punteggio per confrontare la gravità"""
    scores = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
    return scores.get(color, 0)

def parse_alert_color(text):
    if not text: return "green"
    t = str(text).upper()
    if "ROSS" in t: return "red"
    if "ARANC" in t: return "orange"
    if "GIALL" in t: return "yellow"
    return "green"

# --- ANALISI RIGA TABELLA ---
def analizza_riga_rischi(celle):
    """
    Esamina una riga della tabella (Zona, Idro, Temp, Idra).
    Restituisce: (colore_peggiore, descrizione_rischio)
    """
    # Struttura tipica colonne: [0: ZONA, 1: IDRO, 2: TEMP, 3: IDRA, 4: NOTE]
    labels_rischio = {1: "Idrogeologico", 2: "Temporali", 3: "Idraulico"}
    
    max_score = 0
    final_color = "green"
    descrizione_parts = []

    # Itera sulle colonne dei rischi (indici 1, 2, 3)
    for i in range(1, len(celle)):
        if i > 3: break # Ignora colonne note o extra
        
        col_text = str(celle[i]).replace("\n", " ").strip()
        colore = parse_alert_color(col_text)
        score = get_risk_score(colore)

        if score > 0: # Se non è verde
            tipo = labels_rischio.get(i, "Generico")
            
            if score > max_score:
                # Trovato un rischio più grave dei precedenti: resetta e imposta questo
                max_score = score
                final_color = colore
                descrizione_parts = [f"{tipo} ({parse_alert_color(col_text).upper()})"]
            elif score == max_score:
                # Trovato rischio di pari gravità: aggiungi alla lista
                descrizione_parts.append(tipo)

    if max_score == 0:
        return "green", "Nessuna criticità rilevante"
    
    # Unisce le descrizioni (es. "Temporali + Idrogeologico")
    desc_finale = " + ".join(descrizione_parts)
    return final_color, desc_finale

# --- UTILS ---
def extract_validity_info(text):
    start_validity, end_validity = "N/D", "N/D"
    start_match = re.search(r"Inizio validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    end_match = re.search(r"Fine validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    if start_match: start_validity = start_match.group(1).strip()
    if end_match: end_validity = end_match.group(1).strip()
    return start_validity, end_validity

def get_pdf_url():
    try:
        r = requests.get(LIST_URL, headers=FAKE_HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                return BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
    except: pass
    return None

def send_telegram_message(message, file_path=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    try:
        requests.post(url, data=data)
        if file_path:
            url_doc = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
            with open(file_path, 'rb') as f: requests.post(url_doc, data={"chat_id": TELEGRAM_CHAT_ID}, files={'document': f})
    except: pass

def send_push_notification(title, message):
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY: return
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
        "url_bollettino": pdf_url,
        "manual_override": False,
        "zone": {},
        "dettagli_rischi": {}, # NUOVO: Contiene "Rischio Temporali", etc.
        "log_sistema": {"stato": "OK", "msg": "Aggiornato"}
    }

    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            # 1. Estrai date (pagina 1)
            text_p1 = pdf.pages[0].extract_text()
            extracted["validita_inizio"], extracted["validita_fine"] = extract_validity_info(text_p1)
            d_match = re.search(r"DEL (\d{2}/\d{2}/\d{4})", text_p1)
            if d_match: extracted["data_bollettino"] = d_match.group(1)

            # 2. SCAN TOTALE DELLE TABELLE (Oggi + Domani)
            # Scorre tutte le pagine e tutte le tabelle trovate
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        # Pulisci la riga
                        cleaned = [str(c).strip() if c else "" for c in row]
                        
                        # Cerca righe che iniziano con una Zona (BASI ...)
                        if len(cleaned) >= 2 and "BASI" in cleaned[0]:
                            zona = cleaned[0]
                            
                            # Calcola colore e rischio per questa riga specifica
                            colore_riga, desc_riga = analizza_riga_rischi(cleaned)
                            score_riga = get_risk_score(colore_riga)

                            # LOGICA "VINCE IL PEGGIORE":
                            # Se la zona è già stata letta (es. nella tabella di Oggi),
                            # confrontala con questa nuova lettura (es. tabella di Domani).
                            # Tieni quella col rischio più alto.
                            score_attuale = get_risk_score(extracted["zone"].get(zona, "green"))
                            
                            if score_riga > score_attuale:
                                extracted["zone"][zona] = colore_riga
                                extracted["dettagli_rischi"][zona] = desc_riga
                            elif score_riga == score_attuale and zona not in extracted["zone"]:
                                # Primo inserimento (se verde)
                                extracted["zone"][zona] = colore_riga
                                extracted["dettagli_rischi"][zona] = desc_riga

    except Exception as e:
        print(f"Errore: {e}")
        extracted["log_sistema"] = {"stato": "Errore", "msg": str(e)}

    # Verifica se salvare
    if extracted["zone"]:
        # Controllo se i dati sono cambiati o se è forzato
        old_data = {}
        data_changed = True
        if os.path.exists(JSON_FILENAME) and not force:
            try:
                with open(JSON_FILENAME, 'r') as f:
                    old_data = json.load(f)
                    if old_data.get("data_bollettino") == extracted["data_bollettino"]:
                        data_changed = False
            except: pass
        
        if data_changed or force:
            with open(JSON_FILENAME, 'w') as f: json.dump(extracted, f, indent=4)
            
            # Notifiche
            msg = f"🚨 *Bollettino {extracted['data_bollettino']}*\nValidità: {extracted['validita_inizio']}\n\n"
            labels = {"green":"VERDE", "yellow":"GIALLO", "orange":"ARANCIONE", "red":"ROSSO"}
            
            for z in sorted(extracted["zone"].keys()):
                c = extracted["zone"][z]
                dettaglio = extracted["dettagli_rischi"].get(z, "")
                if c != "green": # Dettagli solo se c'è rischio
                    msg += f"🟡 *{z}*: {dettaglio}\n"
                else:
                    msg += f"🟢 *{z}*: {labels[c]}\n"
            
            msg += "\n📍 [Apri Mappa](https://www.formazionesicurezza.org/protezionecivile/bollettino/mappa.html)"
            
            send_telegram_message(msg, PDF_FILENAME)
            send_push_notification(f"Bollettino {extracted['data_bollettino']}", "Dati aggiornati. Controlla i rischi.")
            print("Salvataggio completato.")
        else:
            print("Dati invariati.")

if __name__ == "__main__":
    main()
