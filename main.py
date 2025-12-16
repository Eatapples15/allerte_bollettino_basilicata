import requests
import pdfplumber
import json
import os
import datetime
import re
import sys

# --- CONFIGURAZIONE ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# DEFINIAMO LE ZONE OBBLIGATORIE (Se ne manca una, c'è un problema)
REQUIRED_ZONES = ["BASI A1", "BASI A2", "BASI B", "BASI C", "BASI D", "BASI E1", "BASI E2"]

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
    if not text: return "green"
    text = str(text).upper()
    if "ROSS" in text: return "red"
    if "ARANCION" in text: return "orange"
    if "GIALL" in text: return "yellow"
    return "green"

def get_risk_level(color):
    levels = {"green": 0, "gray": 0, "yellow": 1, "orange": 2, "red": 3}
    return levels.get(color, 0)

def extract_validity_info(text):
    start_validity = "N/D"
    end_validity = "N/D"
    start_match = re.search(r"Inizio validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    end_match = re.search(r"Fine validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    if start_match: start_validity = start_match.group(1).strip()
    if end_match: end_validity = end_match.group(1).strip()
    return start_validity, end_validity

def get_pdf_url():
    try:
        r = requests.get(LIST_URL)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if "Bollettino_Criticita" in a['href']:
                full_url = BASE_URL + a['href'] if not a['href'].startswith('http') else a['href']
                return full_url
    except Exception as e:
        print(f"Errore scraping: {e}")
    return None

def main():
    print("--- INIZIO ELABORAZIONE ---")
    
    pdf_url = get_pdf_url()
    if not pdf_url:
        print("Nessun bollettino trovato.")
        return

    try:
        r = requests.get(pdf_url)
        with open(PDF_FILENAME, 'wb') as f:
            f.write(r.content)
    except Exception as e:
        print(f"Errore download: {e}")
        return

    pdf_date_str = datetime.date.today().strftime("%d/%m/%Y")
    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            text = pdf.pages[0].extract_text()
            date_match = re.search(r"DEL (\d{2}/\d{2}/\d{4})", text)
            if date_match:
                pdf_date_str = date_match.group(1)
    except Exception as e:
        print(f"Errore lettura data PDF: {e}")

    # --- CONTROLLO HUMAN IN THE LOOP ---
    if os.path.exists(JSON_FILENAME):
        try:
            with open(JSON_FILENAME, 'r') as f:
                old_data = json.load(f)
                if old_data.get("data_bollettino") == pdf_date_str and old_data.get("manual_override") is True:
                    print(f"⛔ STOP: Trovato override manuale per il {pdf_date_str}.")
                    return
        except:
            pass
    # -----------------------------------

    extracted_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "data_bollettino": pdf_date_str,
        "validita_inizio": "",
        "validita_fine": "",
        "url_bollettino": pdf_url,
        "manual_override": False,
        "zone": {}
    }

    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            page = pdf.pages[0]
            text = page.extract_text()
            tables = page.extract_tables()
            
            v_start, v_end = extract_validity_info(text)
            extracted_data["validita_inizio"] = v_start
            extracted_data["validita_fine"] = v_end
            
            if tables:
                table = tables[0]
                for row in table:
                    cleaned_row = [str(cell).replace("\n", " ").strip() if cell else "" for cell in row]
                    # Logica migliorata: cerchiamo se la cella CONTIENE una delle zone richieste
                    # Questo aiuta se c'è scritto "BASI  A1" (doppio spazio) o simili
                    found_zone = None
                    if cleaned_row and len(cleaned_row) >= 1:
                        cell_text = cleaned_row[0].upper()
                        for rz in REQUIRED_ZONES:
                            # Rimuoviamo spazi per confronto sicuro "BASIA1" in "BASI A1"
                            if rz.replace(" ", "") in cell_text.replace(" ", ""):
                                found_zone = rz
                                break
                    
                    if found_zone:
                        c1 = parse_alert_color(cleaned_row[1]) if len(cleaned_row) > 1 else "green"
                        c2 = parse_alert_color(cleaned_row[2]) if len(cleaned_row) > 2 else "green"
                        c3 = parse_alert_color(cleaned_row[3]) if len(cleaned_row) > 3 else "green"
                        
                        colors = [c1, c2, c3]
                        max_risk = 0
                        final_color = "green"
                        for c in colors:
                            lvl = get_risk_level(c)
                            if lvl > max_risk:
                                max_risk = lvl
                                final_color = c
                        extracted_data["zone"][found_zone] = final_color
    except Exception as e:
        print(f"❌ Errore parsing PDF: {e}")

    # --- CONTROLLO INTEGRITÀ (MISSING ZONES) ---
    missing_zones = []
    for req_zone in REQUIRED_ZONES:
        if req_zone not in extracted_data["zone"]:
            missing_zones.append(req_zone)
            # Inseriamo un placeholder nel JSON per l'admin
            extracted_data["zone"][req_zone] = "gray" 

    # SALVATAGGIO JSON
    with open(JSON_FILENAME, 'w') as f:
        json.dump(extracted_data, f, indent=4)

    # GESTIONE NOTIFICHE
    color_map_it = { "green": "VERDE", "yellow": "GIALLO", "orange": "ARANCIONE", "red": "ROSSO", "gray": "NON RILEVATO" }
    emoji_map = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴", "gray": "⚪"}

    # SE CI SONO ERRORI -> MESSAGGIO DI ALLERTA
    if missing_zones:
        err_msg = f"⚠️ *ERRORE SISTEMA - INTERVENTO RICHIESTO*\n\n"
        err_msg += f"Il sistema non è riuscito a leggere le seguenti zone dal PDF del {extracted_data['data_bollettino']}:\n"
        for mz in missing_zones:
            err_msg += f"❌ {mz}\n"
        err_msg += "\nI comuni di queste zone appariranno GRIGI sulla mappa.\n"
        err_msg += "👉 *Un operatore deve accedere al pannello Admin e correggere manualmente.*"
        
        send_telegram_message(err_msg, PDF_FILENAME)
        print("⚠️ Allerta Admin inviata per zone mancanti.")
    
    else:
        # TUTTO OK -> MESSAGGIO STANDARD
        msg = f"🚨 *Bollettino criticità regionale del {extracted_data['data_bollettino']}*\n\n"
        msg += f"⬇️ _Inizio:_ {extracted_data['validita_inizio']}\n"
        msg += f"End _Fine:_ {extracted_data['validita_fine']}\n\n"
        
        for zona in REQUIRED_ZONES: # Uso l'ordine standard
            colore_eng = extracted_data["zone"].get(zona, "gray")
            icon = emoji_map.get(colore_eng, "⚪")
            colore_ita = color_map_it.get(colore_eng, colore_eng.upper())
            msg += f"{icon} *{zona}*: {colore_ita}\n"
        
        msg += "\n📍 _Mappa aggiornata sul sito_"
        send_telegram_message(msg, PDF_FILENAME)

if __name__ == "__main__":
    main()
