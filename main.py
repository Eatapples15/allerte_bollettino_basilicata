import requests
import pdfplumber
import json
import os
import datetime
import re
import sys

# --- CONFIGURAZIONE ---
# Ora riprendiamo i dati dai SEGRETI di GitHub per sicurezza
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/"
LIST_URL = "https://centrofunzionale.regione.basilicata.it/it/bollettini-avvisi.php?lt=A"
PDF_FILENAME = "bollettino.pdf"
JSON_FILENAME = "dati_bollettino.json"

def send_telegram_message(message, file_path=None):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERRORE: Token o Chat ID mancanti nei Secrets.")
        return

    url_msg = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    
    try:
        requests.post(url_msg, data=data)
        
        if file_path and os.path.exists(file_path):
            url_doc = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
            with open(file_path, 'rb') as f:
                files = {'document': f}
                requests.post(url_doc, data={"chat_id": TELEGRAM_CHAT_ID}, files=files)
        print("✅ Notifica Telegram inviata.")
    except Exception as e:
        print(f"❌ Errore invio Telegram: {e}")

def parse_alert_color(text):
    """Converte il testo del PDF in codice colore standard"""
    if not text: return "green"
    text = str(text).upper()
    if "ROSS" in text: return "red"
    if "ARANCION" in text: return "orange"
    if "GIALL" in text: return "yellow"
    return "green"

def get_risk_level(color):
    """Assegna un peso numerico al colore per trovare il peggiore"""
    levels = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
    return levels.get(color, 0)

def get_pdf_url():
    """Trova il link del bollettino odierno"""
    try:
        r = requests.get(LIST_URL)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        # Cerca il primo link che contiene "Bollettino_Criticita"
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                full_url = BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
                return full_url
    except Exception as e:
        print(f"Errore scraping: {e}")
    return None

def main():
    print("--- INIZIO ELABORAZIONE BOLLETTINO ---")
    
    # 1. Trova e Scarica PDF
    pdf_url = get_pdf_url()
    if not pdf_url:
        print("Nessun bollettino trovato.")
        return

    print(f"Scaricamento: {pdf_url}")
    try:
        r = requests.get(pdf_url)
        with open(PDF_FILENAME, 'wb') as f:
            f.write(r.content)
    except Exception as e:
        print(f"Errore download: {e}")
        return

    # 2. Parsing del PDF
    extracted_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "url_bollettino": pdf_url,
        "zone": {}
    }

    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            # Di solito la tabella è a pagina 1
            page = pdf.pages[0]
            tables = page.extract_tables()
            
            if tables:
                # Prendiamo la prima tabella trovata
                table = tables[0]
                
                # Iteriamo le righe
                for row in table:
                    # Pulizia della riga
                    cleaned_row = [str(cell).replace("\n", " ").strip() if cell else "" for cell in row]
                    
                    # Cerchiamo le righe che iniziano con "BASI"
                    if len(cleaned_row) >= 2 and "BASI" in cleaned_row[0]:
                        zone_name = cleaned_row[0] # Es: BASI A1
                        
                        # Estraggo i colori dalle colonne (Idrogeologico, Temporali, Idraulico)
                        # Nota: le colonne potrebbero variare leggermente, prendiamo le prime 3 dopo il nome
                        c1 = parse_alert_color(cleaned_row[1]) if len(cleaned_row) > 1 else "green"
                        c2 = parse_alert_color(cleaned_row[2]) if len(cleaned_row) > 2 else "green"
                        c3 = parse_alert_color(cleaned_row[3]) if len(cleaned_row) > 3 else "green"
                        
                        # Calcolo il rischio massimo per colorare la mappa
                        colors = [c1, c2, c3]
                        max_risk = 0
                        final_color = "green"
                        
                        for c in colors:
                            lvl = get_risk_level(c)
                            if lvl > max_risk:
                                max_risk = lvl
                                final_color = c
                        
                        extracted_data["zone"][zone_name] = final_color
            else:
                print("⚠️ Nessuna tabella trovata nel PDF.")

    except Exception as e:
        print(f"❌ Errore parsing PDF: {e}")

    # 3. Controllo se i dati sono validi
    if not extracted_data["zone"]:
        print("⚠️ Attenzione: Nessuna zona estratta. Forse il formato del PDF è cambiato.")
        # Inviamo comunque il PDF ma con un avviso
        send_telegram_message("⚠️ *Attenzione*: Bollettino pubblicato, ma impossibile leggere i dati automatici. Controllare il PDF.", PDF_FILENAME)
        return

    # 4. Salvataggio JSON (Fondamentale per la Mappa)
    with open(JSON_FILENAME, 'w') as f:
        json.dump(extracted_data, f, indent=4)
    print("✅ File JSON aggiornato.")

    # 5. Invio Notifica Telegram Formattata
    emoji_map = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}
    
    msg = f"🚨 *Bollettino Criticità Basilicata*\n"
    msg += f"📅 {extracted_data['ultimo_aggiornamento']}\n\n"
    
    for zona, colore in extracted_data["zone"].items():
        icon = emoji_map.get(colore, "⚪")
        msg += f"{icon} *{zona}*: {colore.upper()}\n"
    
    msg += "\n📍 _Mappa aggiornata sul sito_"
    
    send_telegram_message(msg, PDF_FILENAME)

if __name__ == "__main__":
    main()
