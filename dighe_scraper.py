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
    mesi_ita = {"gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04", "maggio": "05", "giugno": "06",
                "luglio": "07", "agosto": "08", "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12"}
    
    ora = datetime.now()
    mese_str = [k for k, v in mesi_ita.items() if int(v) == ora.month][0]
    url_pagina = f"https://acquedelsudspa.it/servizi/{mese_str}-{ora.year}/"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url_pagina, headers=headers)
        # Trova il link del PDF
        match_pdf = re.findall(r'href="(.*?Bollettino_(\d{4}-\d{2}-\d{2})\.pdf)"', resp.text)
        if not match_pdf: return print("Nessun PDF trovato.")
        
        pdf_url, data_bollettino = match_pdf[-1]
        print(f"Analisi PDF del {data_bollettino}: {pdf_url}")
        
        pdf_res = requests.get(pdf_url, headers=headers)
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            text = pdf.pages[0].extract_text()
            lines = text.split('\n')
            
            nuovi_dati = []
            target_dighe = ["COTUGNO", "PERTUSILLO", "CAMASTRA", "BASENTELLO", "CONZA", "SAETTA", "GIULIANO", "GANNANO", "ACERENZA", "GENZANO"]

            for line in lines:
                line_u = line.upper()
                diga_nome = next((d for d in target_dighe if d in line_u), None)
                
                if diga_nome:
                    numeri = [clean_numeric(n) for n in re.findall(r'[\d\.,]+', line) if clean_numeric(n) != 0 or '0' in n]
                    if len(numeri) < 4: continue

                    try:
                        # Mappatura specifica per i bollettini 2026
                        v_max_lordo = numeri[1]
                        v_netto_attuale = numeri[-3] if len(numeri) >= 9 else numeri[-1]
                        
                        d = {
                            "diga": diga_nome,
                            "quota_max_slm": numeri[0],
                            "volume_max_lordo_mc": v_max_lordo,
                            "quota_attuale_slm": numeri[5] if len(numeri) > 5 else numeri[2],
                            "trend_variazione_cm": numeri[6] if len(numeri) > 6 else 0,
                            "volume_netto_attuale_mc": v_netto_attuale,
                            "pioggia_mm": numeri[-2] if len(numeri) > 2 else 0,
                            "neve_cm": numeri[-1] if len(numeri) > 2 else 0
                        }
                        d["percentuale_riempimento"] = round((v_netto_attuale / v_max_lordo * 100), 2) if v_max_lordo > 0 else 0
                        nuovi_dati.append(d)
                    except: continue

            if nuovi_dati:
                storico = {}
                if os.path.exists(FILE_JSON):
                    with open(FILE_JSON, 'r') as f:
                        try: storico = json.load(f)
                        except: storico = {}
                
                storico[data_bollettino] = {"scraped_at": datetime.now().isoformat(), "dati": nuovi_dati}
                with open(FILE_JSON, 'w') as f:
                    json.dump(storico, f, indent=4)
                print(f"Aggiornato con {len(nuovi_dati)} dighe.")

    except Exception as e: print(f"Errore: {e}")

if __name__ == "__main__":
    scrape_bollettino()
