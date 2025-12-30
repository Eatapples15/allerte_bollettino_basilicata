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
LAST_NOTIFIED_FILE = "last_notified.txt"

COLOR_MAP = {
    "green": {"nome": "VERDE", "icona": "🟢"},
    "yellow": {"nome": "GIALLO", "icona": "🟡"},
    "orange": {"nome": "ARANCIONE", "icona": "🟠"},
    "red": {"nome": "ROSSO", "icona": "🔴"}
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
    max_score, final_color, descrizione_parts = 0, "green", []
    scores = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
    for i in range(1, 4):
        if i >= len(celle): break
        colore = parse_alert_color(celle[i])
        score = scores.get(colore, 0)
        if score > 0:
            tipo = labels_rischio.get(i, "Criticità")
            if score > max_score:
                max_score, final_color, descrizione_parts = score, colore, [tipo]
            elif score == max_score:
                descrizione_parts.append(tipo)
    return final_color, (" + ".join(descrizione_parts) if descrizione_parts else "Assenza di fenomeni significativi")

def get_pdf_url():
    for _ in range(3):
        try:
            r = requests.get(LIST_URL, headers={"User-Agent":"Mozilla/5.0"}, timeout=25)
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                if "Bollettino_Criticita" in a['href']:
                    return BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
        except: time.sleep(5)
    return None

def send_telegram_message(message_tg, message_wa, file_path=None, custom_filename=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_IDS: return
    # Generazione link WhatsApp pre-compilato (senza Markdown)
    whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(message_wa)}"
    full_message_tg = f"{message_tg}\n\n📲 [COPIA E CONDIVIDI SU WHATSAPP]({whatsapp_url})"
    
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                         data={"chat_id": chat_id, "text": full_message_tg, "parse_mode": "Markdown", "disable_web_page_preview": True})
            if file_path:
                with open(file_path, 'rb') as f:
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                 data={"chat_id": chat_id}, files={'document': (custom_filename or file_path, f)})
        except: pass

def main():
    pdf_url = get_pdf_url()
    if not pdf_url: return
    r = requests.get(pdf_url, timeout=60)
    with open(PDF_FILENAME, 'wb') as f: f.write(r.content)

    extracted = {
        "data_bollettino": "",
        "validita_inizio": "N/D",
        "validita_fine": "N/D",
        "zone": {},
        "url_bollettino": pdf_url
    }

    with pdfplumber.open(PDF_FILENAME) as pdf:
        p1_text = pdf.pages[0].extract_text()
        s_match = re.search(r"Inizio validit[àa][:.]?\s*(.*?)(?:\n|$)", p1_text, re.IGNORECASE)
        e_match = re.search(r"Fine validit[àa][:.]?\s*(.*?)(?:\n|$)", p1_text, re.IGNORECASE)
        extracted["validita_inizio"] = s_match.group(1).strip() if s_match else "N/D"
        extracted["validita_fine"] = e_match.group(1).strip() if e_match else "N/D"
        d_match = re.search(r"DEL\s+(\d{2}/\d{2}/\d{4})", p1_text)
        extracted["data_bollettino"] = d_match.group(1) if d_match else datetime.date.today().strftime("%d/%m/%Y")
        
        tables = []
        for page in pdf.pages:
            for table in page.extract_tables():
                if any("BASI" in str(row[0]) for row in table if row and row[0]): tables.append(table)
        
        for i, day_key in enumerate(["oggi", "domani"]):
            if i >= len(tables): break
            for row in tables[i]:
                if row and len(row) > 1 and "BASI" in str(row[0]):
                    zona = str(row[0]).strip().replace("\n", " ")
                    colore, desc = analizza_riga_rischi(row)
                    if zona not in extracted["zone"]: extracted["zone"][zona] = {}
                    extracted["zone"][zona][day_key], extracted["zone"][zona][f"rischio_{day_key}"] = colore, desc

    # CHIAVE IDENTIFICATIVA
    current_key = f"{extracted['data_bollettino']}_{os.path.basename(pdf_url)}"
    extracted["last_sent_key"] = current_key
    extracted["ultimo_aggiornamento"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    # --- AZIONE 1: AGGIORNA SEMPRE IL JSON PER L'APP ---
    with open(JSON_FILENAME, 'w') as f:
        json.dump(extracted, f, indent=4)

    # --- AZIONE 2: INVIO TELEGRAM (CON LINK IPERTESTUALI) ---
    last_notified_key = ""
    if os.path.exists(LAST_NOTIFIED_FILE):
        with open(LAST_NOTIFIED_FILE, "r") as f:
            last_notified_key = f.read().strip()
    elif os.path.exists(JSON_FILENAME):
        try:
            with open(JSON_FILENAME, "r") as f:
                last_notified_key = json.load(f).get("last_sent_key", "")
        except: pass

    if current_key != last_notified_key or FORCE_SEND:
        header = f"🚨 BOLLETTINO PROTEZIONE CIVILE - {extracted['data_bollettino']}\n"
        validity = f"🕒 Validità: {extracted['validita_inizio']} - {extracted['validita_fine']}\n\n"
        
        body = "📋 SITUAZIONE OGGI:\n"
        for z in sorted(extracted["zone"].keys()):
            d = extracted["zone"][z]
            c = COLOR_MAP.get(d.get("oggi"), COLOR_MAP["green"])
            body += f"{c['icona']} {z}: {c['nome']}\n" + (f"   ⚠️ {d.get('rischio_oggi')}\n" if d.get("oggi") != "green" else "")

        footer = "\n🔮 PREVISIONE DOMANI:\n"
        ha_crit = False
        for z in sorted(extracted["zone"].keys()):
            d = extracted["zone"][z]
            if d.get("domani") != "green":
                ha_crit = True
                c = COLOR_MAP.get(d.get("domani"))
                footer += f"{c['icona']} {z}: {c['nome']}\n   ⚠️ {d.get('rischio_domani')}\n"
        if not ha_crit: footer += "🟢 Nessuna criticità prevista.\n"
        
        map_url = "https://www.formazionesicurezza.org/protezionecivile/bollettino/mappa.html"
        # Link Ipertestuali (Markdown per Telegram)
        links_tg = f"\n📍 [Consulta la Mappa]({map_url})\n🔗 [Scarica PDF Originale]({pdf_url})"
        # Link in chiaro (per WhatsApp)
        links_wa = f"\n📍 Mappa: {map_url}\n🔗 PDF: {pdf_url}"
        
        send_telegram_message(
            f"*{header}*{validity}{body}{footer}{links_tg}", 
            f"{header}{validity}{body}{footer}{links_wa}", 
            PDF_FILENAME, 
            f"Bollettino_{extracted['data_bollettino'].replace('/', '-')}.pdf"
        )
        
        with open(LAST_NOTIFIED_FILE, "w") as f:
            f.write(current_key)
        print(f"Notifica inviata: {current_key}")
    else:
        print("Solo JSON aggiornato. Notifica già inviata.")

if __name__ == "__main__":
    main()
