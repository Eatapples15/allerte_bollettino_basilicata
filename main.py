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

# --- NOTIFICHE PUSH (OneSignal) ---
def send_push_notification(title, message):
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY:
        print("⚠️ OneSignal non configurato.")
        return

    header = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_API_KEY}"
    }

    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["Total Subscriptions"],
        "headings": {"en": title, "it": title},
        "contents": {"en": message, "it": message},
        # Nota: La push apre l'app (index), il link telegram apre la mappa specifica
        "url": "https://www.formazionesicurezza.org/protezionecivile/bollettino/index.html"
    }

    try:
        req = requests.post("https://onesignal.com/api/v1/notifications", headers=header, data=json.dumps(payload))
        if req.status_code == 200:
            print("✅ Notifica PUSH inviata.")
        else:
            print(f"❌ Errore Push: {req.text}")
    except Exception as e:
        print(f"❌ Errore connessione OneSignal: {e}")

# --- TELEGRAM ---
def send_telegram_message(message, file_path=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    
    # Codifica il messaggio per l'URL
    # Nota: Non usiamo quote per tutto il body se inviamo via POST data, ma qui prepariamo il link whatsapp
    whatsapp_text = urllib.parse.quote(message.replace('*', '').replace('_', '')) # Rimuovi markdown per whatsapp
    whatsapp_link = f"https://wa.me/?text={whatsapp_text}"
    
    full_message = message + f"\n\n📲 [Inoltra su WhatsApp]({whatsapp_link})"
    
    url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": full_message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    
    try:
        requests.post(url_msg, data=data)
        if file_path and os.path.exists(file_path):
            url_doc = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
            with open(file_path, 'rb') as f:
                files = {'document': f}
                requests.post(url_doc, data={"chat_id": TELEGRAM_CHAT_ID}, files=files)
    except Exception as e: print(f"Errore Telegram: {e}")

# --- PARSING ---
def parse_alert_color(text):
    if not text: return "green"
    text = str(text).upper()
    if "ROSS" in text: return "red"
    if "ARANCION" in text: return "orange"
    if "GIALL" in text: return "yellow"
    return "green"

def get_risk_level(color):
    levels = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
    return levels.get(color, 0)

def extract_validity_info(text):
    start_validity, end_validity = "N/D", "N/D"
    start_match = re.search(r"Inizio validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    end_match = re.search(r"Fine validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    if start_match: start_validity = start_match.group(1).strip()
    if end_match: end_validity = end_match.group(1).strip()
    return start_validity, end_validity

def get_pdf_url():
    try:
        r = requests.get(LIST_URL)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                full_url = BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
                return full_url
    except Exception as e: print(f"Errore scraping PDF: {e}")
    return None

def main():
    print("--- INIZIO ELABORAZIONE BOLLETTINO ---")

    # 1. CONTROLLO MODALITÀ FORZATA
    force_send_active = os.environ.get("FORCE_SEND") == "true"
    if force_send_active:
        print("⚠️ MODALITÀ FORZATA ATTIVA: Le notifiche verranno inviate comunque.")
    
    pdf_url = get_pdf_url()
    if not pdf_url: return

    try:
        r = requests.get(pdf_url)
        with open(PDF_FILENAME, 'wb') as f: f.write(r.content)
    except: return

    pdf_date_str = datetime.date.today().strftime("%d/%m/%Y")
    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            text = pdf.pages[0].extract_text()
            date_match = re.search(r"DEL (\d{2}/\d{2}/\d{4})", text)
            if date_match: pdf_date_str = date_match.group(1)
    except: pass

    # 2. LOGICA DI CONTROLLO (Salta se forzato)
    if os.path.exists(JSON_FILENAME):
        try:
            with open(JSON_FILENAME, 'r') as f:
                old_data = json.load(f)
                if old_data.get("data_bollettino") == pdf_date_str and not old_data.get("manual_override") and not force_send_active:
                    print("✅ Bollettino già processato. Nessuna azione.")
                    return
        except: pass

    extracted_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "data_bollettino": pdf_date_str,
        "validita_inizio": "", "validita_fine": "", "url_bollettino": pdf_url,
        "manual_override": False, "zone": {}
    }

    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            text = pdf.pages[0].extract_text()
            tables = pdf.pages[0].extract_tables()
            v_s, v_e = extract_validity_info(text)
            extracted_data["validita_inizio"], extracted_data["validita_fine"] = v_s, v_e
            
            if tables:
                for row in tables[0]:
                    cleaned = [str(c).replace("\n", " ").strip() if c else "" for c in row]
                    if len(cleaned) >= 2 and "BASI" in cleaned[0]:
                        zone, colors = cleaned[0], [parse_alert_color(c) for c in cleaned[1:4]]
                        max_risk, final = 0, "green"
                        for c in colors:
                            if get_risk_level(c) > max_risk: max_risk, final = get_risk_level(c), c
                        extracted_data["zone"][zone] = final
    except: pass

    if extracted_data["zone"]:
        with open(JSON_FILENAME, 'w') as f: json.dump(extracted_data, f, indent=4)
        
        # Dizionario traduzione colori
        color_labels = {
            "green": "VERDE",
            "yellow": "GIALLO",
            "orange": "ARANCIONE",
            "red": "ROSSO"
        }

        # Costruzione Messaggio Telegram
        msg = f"🚨 *Bollettino {extracted_data['data_bollettino']}*\n"
        msg += f"Validità: {extracted_data['validita_inizio']}\n\n"
        
        for z, c in extracted_data["zone"].items():
            icon = {"green":"🟢","yellow":"🟡","orange":"🟠","red":"🔴"}.get(c,"⚪")
            # Usa il nome italiano (fallback su inglese UPPER se manca)
            label_ita = color_labels.get(c, c.upper())
            msg += f"{icon} *{z}*: {label_ita}\n"
            
        # Link aggiornato richiesto
        msg += "\n📍 [Apri Mappa Interattiva](https://www.formazionesicurezza.org/protezionecivile/bollettino/mappa.html)"
        
        send_telegram_message(msg, PDF_FILENAME)
        
        # Push Notification
        push_title = f"Bollettino {extracted_data['data_bollettino']}"
        push_msg = f"Validità: {extracted_data['validita_inizio']}. Colori aggiornati in mappa."
        send_push_notification(push_title, push_msg)

if __name__ == "__main__":
    main()
