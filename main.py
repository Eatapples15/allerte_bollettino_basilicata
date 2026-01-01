import requests
import pdfplumber
import json
import os
import datetime
import time
import re
import urllib.parse
from bs4 import BeautifulSoup

# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RAW_CHAT_IDS = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_IDS = [cid.strip() for cid in RAW_CHAT_IDS.split(",") if cid.strip()]

BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/"
LIST_URL = "https://centrofunzionale.regione.basilicata.it/it/bollettini-avvisi.php?lt=A"
PDF_FILENAME = "bollettino.pdf"
JSON_FILENAME = "dati_bollettino.json"
# File locale che tiene traccia dell'ultimo invio
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
    try:
        r = requests.get(LIST_URL, headers={"User-Agent":"Mozilla/5.0"}, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                return BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
    except Exception as e:
        print(f"Errore ricerca PDF: {e}")
    return None

def send_telegram(msg_tg, msg_wa, pdf_path):
    if not TELEGRAM_TOKEN: return
    
    # Prepariamo il link WhatsApp per il tasto di condivisione
    wa_link = f"https://wa.me/?text={urllib.parse.quote(msg_wa)}"
    formatted_msg = f"{msg_tg}\n\n📲 [CONDIVIDI SU WHATSAPP]({wa_link})"
    
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            # 1. Invia il testo
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                         data={"chat_id": chat_id, "text": formatted_msg, "parse_mode": "Markdown", "disable_web_page_preview": True})
            # 2. Invia il file PDF
            with open(pdf_path, 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                             data={"chat_id": chat_id}, files={'document': f})
            print(f"✅ Inviato correttamente a {chat_id}")
        except Exception as e:
            print(f"❌ Errore invio a {chat_id}: {e}")

def main():
    pdf_url = get_pdf_url()
    if not pdf_url: return

    # Scarica il PDF
    r = requests.get(pdf_url)
    with open(PDF_FILENAME, 'wb') as f: f.write(r.content)

    extracted = {"zone": {}}
    
    with pdfplumber.open(PDF_FILENAME) as pdf:
        text = pdf.pages[0].extract_text()
        extracted["data_bollettino"] = re.search(r"DEL\s+(\d{2}/\d{2}/\d{4})", text).group(1)
        extracted["validita_inizio"] = re.search(r"Inizio validità[:]?\s*(.*)", text, re.I).group(1).split('\n')[0]
        extracted["validita_fine"] = re.search(r"Fine validità[:]?\s*(.*)", text, re.I).group(1).split('\n')[0]
        
        # Estrazione tabelle (Oggi/Domani)
        found_tables = []
        for p in pdf.pages:
            for t in p.extract_tables():
                if any("BASI" in str(row[0]) for row in t if row): found_tables.append(t)
        
        for i, day in enumerate(["oggi", "domani"]):
            if i < len(found_tables):
                for row in found_tables[i]:
                    if row and "BASI" in str(row[0]):
                        z = str(row[0]).strip().replace('\n',' ')
                        col, desc = analizza_riga_rischi(row)
                        if z not in extracted["zone"]: extracted["zone"][z] = {}
                        extracted["zone"][z][day] = col
                        extracted["zone"][z][f"rischio_{day}"] = desc

    # LOGICA DI CONTROLLO INVIO
    current_key = f"{extracted['data_bollettino']}_{os.path.basename(pdf_url)}"
    
    last_notified = ""
    if os.path.exists(LAST_NOTIFIED_FILE):
        with open(LAST_NOTIFIED_FILE, "r") as f: last_notified = f.read().strip()

    # Salviamo sempre il JSON (per la mappa)
    with open(JSON_FILENAME, 'w') as f: json.dump(extracted, f, indent=4)

    # Inviamo Telegram SOLO se la chiave è diversa
    if current_key != last_notified:
        print(f"🚀 Nuovo bollettino! Invio in corso...")
        
        msg_header = f"🚨 *BOLLETTINO BASILICATA* - {extracted['data_bollettino']}\n"
        msg_val = f"🕒 Validità: {extracted['validita_inizio']} - {extracted['validita_fine']}\n\n"
        
        msg_body = "📋 *SITUAZIONE OGGI:*\n"
        for z in sorted(extracted["zone"].keys()):
            d = extracted["zone"][z]
            c = COLOR_MAP[d['oggi']]
            msg_body += f"{c['icona']} {z}: {c['nome']}\n"
            if d['oggi'] != 'green': msg_body += f"   ⚠️ {d['rischio_oggi']}\n"

        map_link = "https://www.formazionesicurezza.org/protezionecivile/bollettino/map_emb.html"
        links = f"\n📍 [VEDI MAPPA INTERATTIVA]({map_link})\n🔗 [DOWNLOAD PDF]({pdf_url})"
        
        # Testo per WA (senza Markdown)
        msg_wa = f"BOLLETTINO BASILICATA {extracted['data_bollettino']}\nConsulta qui: {map_link}"

        send_telegram(f"{msg_header}{msg_val}{msg_body}{links}", msg_wa, PDF_FILENAME)
        
        # Aggiorna il file di controllo
        with open(LAST_NOTIFIED_FILE, "w") as f: f.write(current_key)
    else:
        print("✅ Bollettino già inviato in precedenza.")

if __name__ == "__main__":
    main()

