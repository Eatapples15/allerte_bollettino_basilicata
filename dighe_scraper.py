import requests
import pdfplumber
import io
import json
import os
import re
from datetime import datetime

FILE_JSON = "storico_invasi.json"

def clean_numeric(value):
    if not value: return 0.0
    s = str(value).replace(' ', '').replace('----------', '0').strip()
    s = re.sub(r'[^\d,.-]', '', s)
    try:
        if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
        elif ',' in s: s = s.replace(',', '.')
        return float(s)
    except: return 0.0

def scrape_bollettino():
    # URL dinamico del mese
    mesi = {1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 6: "giugno",
            7: "luglio", 8: "agosto", 9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"}
    ora = datetime.now()
    url_pagina = f"https://acquedelsudspa.it/servizi/{mesi[ora.month]}-{ora.year}/"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url_pagina, headers=headers)
        soup = re.findall(r'href="(.*?Bollettino_.*?\.pdf)"', resp.text)
        if not soup: return print("Nessun PDF trovato.")
        
        pdf_url = soup[-1]
        data_bollettino = re.search(r'(\d{4}-\d{2}-\d{2})', pdf_url).group(1)
        print(f"Analisi PDF: {pdf_url}")
        
        pdf_res = requests.get(pdf_url, headers=headers)
        
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            text = pdf.pages[0].extract_text()
            lines = text.split('\n')
            
            nuovi_dati = []
            # Lista delle dighe da cercare (nomi abbreviati per match più facile)
            target_dighe = ["COTUGNO", "PERTUSILLO", "CAMASTRA", "BASENTELLO", "CONZA", "SAETTA", "GIULIANO", "GANNANO", "ACERENZA", "GENZANO"]

            for line in lines:
                line_upper = line.upper()
                # Cerchiamo se la riga contiene una delle dighe
                diga_trovata = next((d for d in target_dighe if d in line_upper), None)
                
                if diga_trovata:
                    # Estraiamo tutti i numeri dalla riga (es: 252,00 480.700.000 ...)
                    # Cerchiamo sequenze di cifre con punti e virgole
                    numeri_testo = re.findall(r'[\d\.,]+', line)
                    numeri = [clean_numeric(n) for n in numeri_testo if clean_numeric(n) != 0 or n == '0']
                    
                    if len(numeri) < 4: continue # Salta righe con troppi pochi dati

                    # Mappatura euristica (adattata ai PDF 2026)
                    # In genere l'ordine è: 0:QuotaMax, 1:VolumeMax, ..., penultimo:Pioggia, ultimo:Neve
                    try:
                        # Cerchiamo il volume netto (che è un numero grande, tipicamente verso la fine)
                        # Spesso è l'ultimo numero prima di Pioggia e Neve
                        v_netto = numeri[-3] if len(numeri) >= 5 else numeri[-1]
                        v_max = numeri[1] if len(numeri) > 1 else 0
                        
                        d = {
                            "diga": diga_trovata,
                            "quota_max_slm": numeri[0],
                            "volume_max_lordo_mc": v_max,
                            "quota_attuale_slm": numeri[5] if len(numeri) > 5 else (numeri[2] if len(numeri) > 2 else 0),
                            "trend_variazione_cm": numeri[6] if len(numeri) > 6 else 0,
                            "volume_netto_attuale_mc": v_netto,
                            "pioggia_mm": numeri[-2] if len(numeri) > 2 else 0,
                            "neve_cm": numeri[-1] if len(numeri) > 2 else 0,
                        }
                        # Percentuale corretta
                        d["percentuale_riempimento"] = round((d["volume_netto_attuale_mc"] / d["volume_max_lordo_mc"] * 100), 2) if d["volume_max_lordo_mc"] > 100 else 0
                        
                        nuovi_dati.append(d)
                        print(f"OK: {diga_trovata} -> Netto: {v_netto} mc")
                    except Exception as e:
                        print(f"Errore su {diga_trovata}: {e}")

            # Salvataggio
            storico = {}
            if os.path.exists(FILE_JSON):
                with open(FILE_JSON, 'r') as f:
                    try: storico = json.load(f)
                    except: storico = {}
            
            storico[data_bollettino] = {"scraped_at": datetime.now().isoformat(), "dati": nuovi_dati}
            with open(FILE_JSON, 'w') as f:
                json.dump(storico, f, indent=4)
            
            print(f"Fine. Trovate {len(nuovi_dati)} dighe su {len(target_dighe)}.")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape_bollettino()
