
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
# Inserisci gli ID separati da virgola (es: "-100123,-100456")
RAW_CHAT_IDS = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_IDS = [cid.strip() for cid in RAW_CHAT_IDS.split(",") if cid.strip()]
FORCE_SEND = os.environ.get("FORCE_SEND") == "true"

BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/"
LIST_URL = "https://centrofunzionale.regione.basilicata.it/it/bollettini-avvisi.php?lt=A"
PDF_FILENAME = "bollettino.pdf"
JSON_FILENAME = "dati_bollettino.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/119.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0"
]

# Variabili di stato per lo scheduling intelligente
BOLLETTINO_OGGI_TROVATO = False
DATA_ULTIMO_CONTROLLO = ""

# --- LOGICA DI SCHEDULING ---
def get_wait_time():
    global BOLLETTINO_OGGI_TROVATO, DATA_ULTIMO_CONTROLLO
    now = datetime.datetime.now()
    hour = now.hour
    minute = now.minute
    today_str = now.strftime("%d/%m/%Y")

    # Reset se è un nuovo giorno
    if DATA_ULTIMO_CONTROLLO != today_str:
        BOLLETTINO_OGGI_TROVATO = False
        DATA_ULTIMO_CONTROLLO = today_str

    # 1. FINESTRA DI CACCIA (11:30 - 14:30)
    # Se non abbiamo ancora trovato il bollettino di oggi, controlliamo ogni 10 min
    if (11 <= hour <= 14) and not BOLLETTINO_OGGI_TROVATO:
        if hour == 11 and minute < 30: # Prima delle 11:30 aspetta un po' di più
            wait = 30 * 60
        else:
            print("-> Stato: HUNTING (Ricerca bollettino odierno...)")
            wait = 10 * 60
    
    # 2. FINESTRA VIGILANZA POMERIDIANA (15:00 - 19:00)
    # Bollettino già trovato o primo pomeriggio: controlla ogni ora per edizioni straordinarie
    elif 15 <= hour < 19:
        print("-> Stato: MONITORING (Vigilanza per aggiornamenti straordinari)")
        wait = 60 * 60
    
    # 3. FINESTRA NOTTURNA / MATTUTINA
    else:
        print("-> Stato: RELAX (Frequenza ridotta)")
        wait = 120 * 60 # 2 ore

    # Jitter anti-bot (aggiunge 1-4 minuti casuali)
    return wait + random.randint(60, 240)

# --- LOGICA DI PARSING ---
def get_risk_score(color):
    return {"green": 0, "yellow": 1, "orange": 2, "red": 3}.get(color, 0)

def parse_alert_color(text):
    if not text: return "green"
    t = str(text).upper()
    if "ROSS" in t: return "red"
    if "ARANC" in t: return "orange"
    if "GIALL" in t: return "yellow"
    return "green"

def analizza_riga_rischi(celle):
    labels_rischio = {1: "Criticità Idrogeologica", 2: "Criticità Idrogeologica per Temporali", 3: "Criticità Idraulica"}
    max_score = 0
    final_color = "green"
    descrizione_parts = []
    for i in range(1, len(celle)):
        if i > 3: break 
        colore = parse_alert_color(celle[i])
        score = get_risk_score(colore)
        if score > 0: 
            tipo = labels_rischio.get(i, "Criticità Generica")
            if score > max_score:
                max_score, final_color, descrizione_parts = score, colore, [tipo]
            elif score == max_score and tipo not in descrizione_parts:
                descrizione_parts.append(tipo)
    return final_color, (" + ".join(descrizione_parts) if descrizione_parts else "Assenza di fenomeni significativi")

def get_pdf_url():
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS), "Referer": BASE_URL}
        r = requests.get(LIST_URL, headers=headers, timeout=25)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                return BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
    except: pass
    return None

def send_telegram_message(message, file_path=None, custom_filename=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_IDS: return
    clean_text = message.replace('*', '').replace('_', '').replace('`', '')
    whatsapp_encoded = urllib.parse.quote(clean_text)
    full_message = message + f"\n\n📲 [Condividi su WhatsApp](https://wa.me/?text={whatsapp_encoded})"
    
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            # Testo
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          data={"chat_id": chat_id, "text": full_message, "parse_mode": "Markdown", "disable_web_page_preview": True})
            # PDF
            if file_path:
                with open(file_path, 'rb') as f:
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                                  data={"chat_id": chat_id}, files={'document': (custom_filename or file_path, f, 'application/pdf')})
            time.sleep(1) # Delay tra i canali
        except Exception as e: print(f"Errore Telegram ({chat_id}): {e}")

def scrape_and_notify():
    global BOLLETTINO_OGGI_TROVATO
    pdf_url = get_pdf_url()
    if not pdf_url: return

    try:
        r = requests.get(pdf_url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=60)
        with open(PDF_FILENAME, 'wb') as f: f.write(r.content)
    except: return

    extracted = {"ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "url_bollettino": pdf_url, "zone": {}}

    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            p1_text = pdf.pages[0].extract_text()
            
            # Estrazione Date
            s_match = re.search(r"Inizio validit[àa][:.]?\s*(.*?)(?:\n|$)", p1_text, re.IGNORECASE)
            e_match = re.search(r"Fine validit[àa][:.]?\s*(.*?)(?:\n|$)", p1_text, re.IGNORECASE)
            extracted["validita_inizio"] = s_match.group(1).strip() if s_match else "N/D"
            extracted["validita_fine"] = e_match.group(1).strip() if e_match else "N/D"
            
            d_match = re.search(r"DEL\s+(\d{2}/\d{2}/\d{4})", p1_text)
            extracted["data_bollettino"] = d_match.group(1) if d_match else datetime.date.today().strftime("%d/%m/%Y")

            # Verifica se è il bollettino di oggi per lo scheduling
            if extracted["data_bollettino"] == datetime.date.today().strftime("%d/%m/%Y"):
                BOLLETTINO_OGGI_TROVATO = True

            tables_found = []
            for page in pdf.pages:
                for table in page.extract_tables():
                    if any("BASI" in str(row[0]) for row in table if row and len(row) > 0 and row[0]):
                        tables_found.append(table)

            giorni = ["oggi", "domani"]
            for i, table in enumerate(tables_found[:2]):
                current_day = giorni[i]
                for row in table:
                    cleaned = [str(c).strip() if c else "" for c in row]
                    if len(cleaned) >= 2 and "BASI" in cleaned[0]:
                        zona = cleaned[0]
                        colore, desc = analizza_riga_rischi(cleaned)
                        if zona not in extracted["zone"]:
                            extracted["zone"][zona] = {"oggi": "green", "rischio_oggi": "N/D", "domani": "green", "rischio_domani": "N/D"}
                        extracted["zone"][zona][current_day], extracted["zone"][zona][f"rischio_{current_day}"] = colore, desc
    except Exception as e: print(f"Errore PDF: {e}")

    # Controllo cambiamenti
    data_changed = True
    if os.path.exists(JSON_FILENAME) and not FORCE_SEND:
        try:
            with open(JSON_FILENAME, 'r') as f:
                if json.load(f).get("data_bollettino") == extracted["data_bollettino"]:
                    data_changed = False
        except: pass
    
    if data_changed or FORCE_SEND:
        with open(JSON_FILENAME, 'w') as f: json.dump(extracted, f, indent=4)
        
        str_oggi = extracted['data_bollettino']
        try:
            str_domani = (datetime.datetime.strptime(str_oggi, "%d/%m/%Y") + timedelta(days=1)).strftime("%d/%m/%Y")
        except: str_domani = "N/D"

        msg = f"🚨 *Bollettino Protezione Civile {str_oggi}*\n🕒 Validità: {extracted['validita_inizio']}\n\n"
        msg += f"📋 *SITUAZIONE OGGI ({str_oggi}):*\n"
        for z in sorted(extracted["zone"].keys()):
            d = extracted["zone"][z]
            icon = {"green":"🟢","yellow":"🟡","orange":"🟠","red":"🔴"}.get(d["oggi"],"⚪")
            msg += f"{icon} *{z}*: {d['oggi'].upper()}\n" + (f"   ⚠️ _{d['rischio_oggi']}_\n" if d['oggi'] != "green" else "")

        msg += f"\n🔮 *PREVISIONE DOMANI ({str_domani}):*\n"
        crit_dom = False
        for z in sorted(extracted["zone"].keys()):
            d = extracted["zone"][z]
            if d["domani"] != "green":
                crit_dom = True
                icon = {"green":"🟢","yellow":"🟡","orange":"🟠","red":"🔴"}.get(d["domani"],"⚪")
                msg += f"{icon} *{z}*: {d['domani'].upper()}\n   ⚠️ _{d['rischio_domani']}_\n"
        if not crit_dom: msg += "🟢 Nessuna criticità significativa prevista.\n"

        msg += f"\n🌐 [Scarica PDF]({extracted['url_bollettino']})\n📍 [Mappa Interattiva](https://www.formazionesicurezza.org/protezionecivile/bollettino/mappa.html)"
        send_telegram_message(msg, PDF_FILENAME, f"Bollettino_{str_oggi.replace('/', '-')}.pdf")
        print("Notifiche inviate a tutti i canali.")
    else: print("Dati già aggiornati.")

# --- LOOP PRINCIPALE ---
if __name__ == "__main__":
    while True:
        try:
            scrape_and_notify()
        except Exception as e: print(f"Errore generale: {e}")
        
        wait_sec = get_wait_time()
        print(f"Prossimo controllo tra {wait_sec // 60} minuti.")
        time.sleep(wait_sec)
