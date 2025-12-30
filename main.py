import requests
import pdfplumber
import json
import os
import datetime
import time
import random
import re
import urllib.parse
from datetime import timedelta
from bs4 import BeautifulSoup

# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAW_CHAT_IDS = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_IDS = [cid.strip() for cid in RAW_CHAT_IDS.split(",") if cid.strip()]
FORCE_SEND = os.environ.get("FORCE_SEND") == "true"

BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/"
LIST_URL = "https://centrofunzionale.regione.basilicata.it/it/bollettini-avvisi.php?lt=A"
PDF_FILENAME = "bollettino.pdf"
JSON_FILENAME = "dati_bollettino.json"

# Dizionario traduzione colori e icone
COLOR_MAP = {
    "green": {"nome": "VERDE", "icona": "🟢", "desc": "Criticità Assente"},
    "yellow": {"nome": "GIALLO", "icona": "🟡", "desc": "Criticità Ordinaria"},
    "orange": {"nome": "ARANCIONE", "icona": "🟠", "desc": "Criticità Moderata"},
    "red": {"nome": "ROSSO", "icona": "🔴", "desc": "Criticità Elevata"}
}

def parse_alert_color(text):
    if not text: return "green"
    t = str(text).upper()
    if "ROSS" in t: return "red"
    if "ARANC" in t: return "orange"
    if "GIALL" in t: return "yellow"
    return "green"

def analizza_riga_rischi(celle):
    labels_rischio = {1: "Idrogeologico", 2: "Temporali", 3: "Idraulico"}
    max_score = 0
    final_color = "green"
    descrizione_parts = []
    scores = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
    
    for i in range(1, 4):
        if i >= len(celle): break
        colore = parse_alert_color(celle[i])
        score = scores.get(colore, 0)
        if score > 0:
            tipo = labels_rischio.get(i, "Criticità")
            if score > max_score:
                max_score, final_color = score, colore
                descrizione_parts = [tipo]
            elif score == max_score:
                descrizione_parts.append(tipo)
                
    return final_color, (" + ".join(descrizione_parts) if descrizione_parts else "Assenza di fenomeni significativi")

def get_pdf_url():
    # Rafforziamo la lettura provando fino a 3 volte in caso di timeout
    for attempt in range(3):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0 Safari/537.36"}
            r = requests.get(LIST_URL, headers=headers, timeout=25)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                if "Bollettino_Criticita" in a['href']:
                    full_url = BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
                    return full_url
        except Exception as e:
            print(f"Tentativo {attempt+1} fallito: {e}")
            time.sleep(5)
    return None

def send_telegram_message(message, file_path=None, custom_filename=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_IDS: return
    clean_text = message.replace('*', '').replace('_', '')
    whatsapp_encoded = urllib.parse.quote(clean_text)
    full_message = message + f"\n\n📲 [Condividi su WhatsApp](https://wa.me/?text={whatsapp_encoded})"
    
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                         data={"chat_id": chat_id, "text": full_message, "parse_mode": "Markdown", "disable_web_page_preview": True})
            if file_path:
                with open(file_path, 'rb') as f:
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                 data={"chat_id": chat_id}, files={'document': (custom_filename or file_path, f)})
            time.sleep(1)
        except Exception as e: print(f"Errore Telegram: {e}")

def scrape_and_notify():
    pdf_url = get_pdf_url()
    if not pdf_url: 
        print("Impossibile recuperare l'URL del PDF.")
        return

    r = requests.get(pdf_url, timeout=60)
    with open(PDF_FILENAME, 'wb') as f: f.write(r.content)

    extracted = {"data_bollettino": "", "zone": {}, "url_bollettino": pdf_url}

    with pdfplumber.open(PDF_FILENAME) as pdf:
        p1_text = pdf.pages[0].extract_text()
        d_match = re.search(r"DEL\s+(\d{2}/\d{2}/\d{4})", p1_text)
        extracted["data_bollettino"] = d_match.group(1) if d_match else datetime.date.today().strftime("%d/%m/%Y")
        
        tables = []
        for page in pdf.pages:
            found_tables = page.extract_tables()
            for table in found_tables:
                if any("BASI" in str(row[0]) for row in table if row and row[0]):
                    tables.append(table)

        giorni = ["oggi", "domani"]
        for i, table in enumerate(tables[:2]):
            day_key = giorni[i]
            for row in table:
                if row and len(row) > 1 and "BASI" in str(row[0]):
                    zona = str(row[0]).strip().replace("\n", " ")
                    colore, desc = analizza_riga_rischi(row)
                    if zona not in extracted["zone"]: extracted["zone"][zona] = {}
                    extracted["zone"][zona][day_key] = colore
                    extracted["zone"][zona][f"rischio_{day_key}"] = desc

    # --- LOGICA ANTI-RIPETIZIONE ---
    # Controlliamo se abbiamo già inviato questo specifico bollettino (per data e URL)
    sent_key = f"{extracted['data_bollettino']}_{os.path.basename(pdf_url)}"
    already_sent = False
    
    if os.path.exists(JSON_FILENAME):
        with open(JSON_FILENAME, 'r') as f:
            old_data = json.load(f)
            # Se la data e l'URL coincidono, il bollettino è identico
            if old_data.get("last_sent_key") == sent_key:
                already_sent = True

    if not already_sent or FORCE_SEND:
        extracted["last_sent_key"] = sent_key
        with open(JSON_FILENAME, 'w') as f: json.dump(extracted, f, indent=4)
        
        data_b = extracted['data_bollettino']
        msg = f"🚨 *BOLLETTINO PROTEZIONE CIVILE - {data_b}*\n\n"
        
        # Oggi
        msg += f"📋 *SITUAZIONE OGGI:*\n"
        for z in sorted(extracted["zone"].keys()):
            d = extracted["zone"][z]
            c_info = COLOR_MAP.get(d.get("oggi"), COLOR_MAP["green"])
            msg += f"{c_info['icona']} *{z}*: {c_info['nome']}\n"
            if d.get("oggi") != "green": msg += f"   ⚠️ _{d.get('rischio_oggi')}_\n"

        # Domani
        msg += f"\n🔮 *PREVISIONE DOMANI:*\n"
        ha_crit_domani = False
        for z in sorted(extracted["zone"].keys()):
            d = extracted["zone"][z]
            if d.get("domani") != "green":
                ha_crit_domani = True
                c_info = COLOR_MAP.get(d.get("domani"))
                msg += f"{c_info['icona']} *{z}*: {c_info['nome']}\n   ⚠️ _{d.get('rischio_domani')}_\n"
        
        if not ha_crit_domani: msg += "🟢 Nessuna criticità prevista.\n"
        
        msg += f"\n🔗 [Scarica PDF originale]({pdf_url})"
        
        send_telegram_message(msg, PDF_FILENAME, f"Bollettino_{data_b.replace('/', '-')}.pdf")
        print(f"Bollettino {sent_key} inviato.")
    else:
        print(f"Bollettino {sent_key} già inviato in precedenza. Salto.")

if __name__ == "__main__":
    scrape_and_notify()
