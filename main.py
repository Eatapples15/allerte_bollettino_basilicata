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
# OneSignal rimosso o lasciato vuoto se non usato
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
    scores = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
    return scores.get(color, 0)

def parse_alert_color(text):
    if not text: return "green"
    t = str(text).upper()
    if "ROSS" in t: return "red"
    if "ARANC" in t: return "orange"
    if "GIALL" in t: return "yellow"
    return "green"

def analizza_riga_rischi(celle):
    # Diciture complete come richiesto
    labels_rischio = {
        1: "Criticità Idrogeologica", 
        2: "Criticità Idrogeologica per Temporali", 
        3: "Criticità Idraulica"
    }
    
    max_score = 0
    final_color = "green"
    descrizione_parts = []

    for i in range(1, len(celle)):
        if i > 3: break 
        col_text = str(celle[i]).replace("\n", " ").strip()
        colore = parse_alert_color(col_text)
        score = get_risk_score(colore)

        if score > 0: 
            tipo = labels_rischio.get(i, "Criticità Generica")
            
            if score > max_score:
                max_score = score
                final_color = colore
                descrizione_parts = [tipo]
            elif score == max_score:
                if tipo not in descrizione_parts:
                    descrizione_parts.append(tipo)

    if max_score == 0: 
        return "green", "Assenza di fenomeni significativi"
    
    desc_finale = " + ".join(descrizione_parts)
    return final_color, desc_finale

# --- UTILS ---
def extract_validity_info(text):
    start, end = "N/D", "N/D"
    s_match = re.search(r"Inizio validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    e_match = re.search(r"Fine validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    if s_match: start = s_match.group(1).strip()
    if e_match: end = e_match.group(1).strip()
    return start, end

def get_pdf_url():
    try:
        r = requests.get(LIST_URL, headers=FAKE_HEADERS, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                return BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
    except: pass
    return None

# MODIFICATO: Accetta custom_filename
def send_telegram_message(message, file_path=None, custom_filename=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    
    clean_text = message.replace('*', '').replace('_', '').replace('`', '')
    whatsapp_encoded = urllib.parse.quote(clean_text)
    full_message = message + f"\n\n📲 [Condividi su WhatsApp](https://wa.me/?text={whatsapp_encoded})"
    
    url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": full_message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    
    try:
        requests.post(url_msg, data=data)
        
        if file_path:
            url_doc = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
            with open(file_path, 'rb') as f:
                # Se c'è un nome personalizzato, lo usiamo nella tupla dei file
                if custom_filename:
                    files_payload = {'document': (custom_filename, f, 'application/pdf')}
                else:
                    files_payload = {'document': f}
                
                requests.post(url_doc, data={"chat_id": TELEGRAM_CHAT_ID}, files=files_payload)
    except Exception as e: 
        print(f"Errore invio Telegram: {e}")

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
        "log_sistema": {"stato": "OK", "msg": "Aggiornato"}
    }

    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            p1_text = pdf.pages[0].extract_text()
            extracted["validita_inizio"], extracted["validita_fine"] = extract_validity_info(p1_text)
            
            d_match = re.search(r"PROT.*DEL\s+(\d{2}/\d{2}/\d{4})", p1_text)
            if not d_match:
                d_match = re.search(r"DEL\s+(\d{2}/\d{2}/\d{4})", p1_text)
            
            if d_match: extracted["data_bollettino"] = d_match.group(1)

            tables_found = []
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    valid_rows = 0
                    for row in table:
                        clean_row = [str(c).strip() if c else "" for c in row]
                        if len(clean_row) >= 2 and "BASI" in clean_row[0]:
                            valid_rows += 1
                    if valid_rows > 3:
                        tables_found.append(table)

            giorni = ["oggi", "domani"]
            print(f"Tabelle trovate: {len(tables_found)}")

            for i, table in enumerate(tables_found):
                if i >= 2: break 
                current_day = giorni[i]
                
                for row in table:
                    cleaned = [str(c).strip() if c else "" for c in row]
                    if len(cleaned) >= 2 and "BASI" in cleaned[0]:
                        zona = cleaned[0]
                        colore, desc = analizza_riga_rischi(cleaned)
                        
                        if zona not in extracted["zone"]:
                            extracted["zone"][zona] = {
                                "oggi": "green", "rischio_oggi": "Criticità Assente",
                                "domani": "green", "rischio_domani": "Criticità Assente"
                            }
                        
                        extracted["zone"][zona][current_day] = colore
                        extracted["zone"][zona][f"rischio_{current_day}"] = desc

    except Exception as e:
        print(f"Errore: {e}")
        extracted["log_sistema"] = {"stato": "Errore", "msg": str(e)}

    if extracted["zone"]:
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
            
            labels_it = {"green":"VERDE", "yellow":"GIALLO", "orange":"ARANCIONE", "red":"ROSSO"}
            
            msg = f"🚨 *Bollettino Protezione Civile {extracted['data_bollettino']}*\n"
            msg += f"🕒 Validità: {extracted['validita_inizio']}\n\n"
            
            # OGGI
            msg += "📋 *SITUAZIONE OGGI:*\n"
            for z in sorted(extracted["zone"].keys()):
                dati = extracted["zone"][z]
                c_oggi = dati["oggi"]
                icon = {"green":"🟢","yellow":"🟡","orange":"🟠","red":"🔴"}.get(c_oggi,"⚪")
                txt = labels_it.get(c_oggi, "N/D")
                detail = dati['rischio_oggi']
                
                if c_oggi != "green":
                    msg += f"{icon} *{z}*: {txt}\n   ⚠️ _{detail}_\n"
                else:
                    msg += f"{icon} *{z}*: {txt}\n"

            # DOMANI
            msg += "\n🔮 *PREVISIONE DOMANI:*\n"
            crit_domani = False
            for z in sorted(extracted["zone"].keys()):
                dati = extracted["zone"][z]
                c_dom = dati["domani"]
                if c_dom != "green":
                    crit_domani = True
                    icon = {"green":"🟢","yellow":"🟡","orange":"🟠","red":"🔴"}.get(c_dom,"⚪")
                    txt = labels_it.get(c_dom, "N/D")
                    detail = dati['rischio_domani']
                    msg += f"{icon} *{z}*: {txt}\n   ⚠️ _{detail}_\n"
            
            if not crit_domani:
                msg += "🟢 Nessuna criticità significativa prevista.\n"

            msg += f"\n🌐 [Scarica Bollettino PDF]({extracted['url_bollettino']})"
            msg += "\n📍 [Mappa Interattiva](https://www.formazionesicurezza.org/protezionecivile/bollettino/mappa.html)"
            
            # --- CREAZIONE NOME FILE PDF PERSONALIZZATO ---
            # Sostituiamo gli slash con trattini per evitare errori nel filesystem
            safe_date = extracted['data_bollettino'].replace("/", "-")
            custom_pdf_name = f"Bollettino del {safe_date}.pdf"

            send_telegram_message(msg, PDF_FILENAME, custom_pdf_name)
            print("Salvataggio completato e notifica inviata.")
        else:
            print("Dati invariati.")

if __name__ == "__main__":
    main()
