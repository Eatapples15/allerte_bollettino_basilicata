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
    """Peso numerico del colore"""
    levels = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
    return levels.get(color, 0)

def extract_validity_info(text):
    """Estrae orari di validità"""
    start_validity = "N/D"
    end_validity = "N/D"
    
    start_match = re.search(r"Inizio validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    end_match = re.search(r"Fine validit[àa][:.]?\s*(.*?)(?:\n|$)", text, re.IGNORECASE)
    
    if start_match: start_validity = start_match.group(1).strip()
    if end_match: end_validity = end_match.group(1).strip()
    
    return start_validity, end_validity

def get_pdf_url():
    """Trova il link del bollettino odierno"""
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
    
    # 1. Trova l'URL
    pdf_url = get_pdf_url()
    if not pdf_url:
        print("Nessun bollettino trovato online.")
        return

    # 2. Scarica il PDF (Sovrascrittura locale temporanea)
    try:
        r = requests.get(pdf_url)
        with open(PDF_FILENAME, 'wb') as f:
            f.write(r.content)
    except Exception as e:
        print(f"Errore download: {e}")
        return

    # 3. Estrai la DATA dal PDF appena scaricato
    # Questo è il cuore del controllo anti-duplicati
    pdf_date_str = datetime.date.today().strftime("%d/%m/%Y") # Default fallback
    try:
        with pdfplumber.open(PDF_FILENAME) as pdf:
            text = pdf.pages[0].extract_text()
            # Cerca data nel formato GG/MM/AAAA dopo la parola "DEL"
            # Es: PROT. ... DEL 16/12/2025
            date_match = re.search(r"DEL (\d{2}/\d{2}/\d{4})", text)
            if date_match:
                pdf_date_str = date_match.group(1)
    except Exception as e:
        print(f"Errore lettura preliminare PDF: {e}")

    print(f"Data rilevata nel PDF online: {pdf_date_str}")

    # 4. CONTROLLO DUPLICATI & HUMAN OVERRIDE
    # Confrontiamo la data del PDF appena scaricato con quella salvata nel JSON su GitHub
    if os.path.exists(JSON_FILENAME):
        try:
            with open(JSON_FILENAME, 'r') as f:
                old_data = json.load(f)
                last_saved_date = old_data.get("data_bollettino")
                
                # CASO A: Le date coincidono -> ABBIAMO GIÀ FATTO QUESTO BOLLETTINO
                if last_saved_date == pdf_date_str:
                    print(f"✅ STOP: Il bollettino del {pdf_date_str} è già stato processato e inviato.")
                    
                    # Controllo extra: se c'era un override manuale, a maggior ragione non tocchiamo nulla
                    if old_data.get("manual_override") is True:
                        print("Nota: È attivo anche un blocco manuale operatore.")
                    
                    # Uscita pulita senza errori
                    return

        except Exception as e:
            print(f"Errore lettura JSON precedente (procedo come se fosse nuovo): {e}")

    # Se siamo qui, significa che la data è NUOVA. Procediamo.
    print(f"🆕 Trovato NUOVO bollettino ({pdf_date_str}). Inizio elaborazione...")

    # 5. Parsing Completo
    extracted_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "data_bollettino": pdf_date_str,
        "validita_inizio": "",
        "validita_fine": "",
        "url_bollettino": pdf_url,
        "manual_override": False, # Reset su nuovo file
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
                    if len(cleaned_row) >= 2 and "BASI" in cleaned_row[0]:
                        zone_name = cleaned_row[0]
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
                        extracted_data["zone"][zone_name] = final_color
            else:
                print("⚠️ Nessuna tabella trovata nel PDF.")

    except Exception as e:
        print(f"❌ Errore parsing PDF: {e}")

    # Validazione
    if not extracted_data["zone"]:
        send_telegram_message("⚠️ *Attenzione*: Impossibile leggere i dati automatici. Verificare PDF.", PDF_FILENAME)
        return

    # 6. Salvataggio JSON (Committa su GitHub)
    with open(JSON_FILENAME, 'w') as f:
        json.dump(extracted_data, f, indent=4)
    print("✅ File JSON aggiornato.")

    # 7. Invio Telegram (Solo ora!)
    color_map_it = { "green": "VERDE", "yellow": "GIALLO", "orange": "ARANCIONE", "red": "ROSSO" }
    emoji_map = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴"}
    
    msg = f"🚨 *Bollettino criticità regionale del {extracted_data['data_bollettino']}*\n\n"
    msg += f"⬇️ _Inizio:_ {extracted_data['validita_inizio']}\n"
    msg += f"End _Fine:_ {extracted_data['validita_fine']}\n\n"
    
    for zona, colore_eng in extracted_data["zone"].items():
        icon = emoji_map.get(colore_eng, "⚪")
        colore_ita = color_map_it.get(colore_eng, colore_eng.upper())
        msg += f"{icon} *{zona}*: {colore_ita}\n"
    
    msg += "\n📍 _Mappa aggiornata sul sito_"
    
    send_telegram_message(msg, PDF_FILENAME)

if __name__ == "__main__":
    main()
