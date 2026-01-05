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
        match_pdf = re.findall(r'href="(.*?Bollettino_(\d{4}-\d{2}-\d{2})\.pdf)"', resp.text)
        if not match_pdf: return print("Nessun PDF trovato.")
        
        pdf_url, data_bollettino = match_pdf[-1]
        pdf_res = requests.get(pdf_url, headers=headers)
        
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            page = pdf.pages[0]
            width = page.width
            words = page.extract_words()
            
            info_invasi = {
                "COTUGNO": {"max_v": 480700000, "max_q": 252.0},
                "PERTUSILLO": {"max_v": 155000000, "max_q": 531.0},
                "CAMASTRA": {"max_v": 18418128, "max_q": 531.6},
                "BASENTELLO": {"max_v": 33039968, "max_q": 269.0},
                "CONZA": {"max_v": 61813380, "max_q": 434.8},
                "SAETTA": {"max_v": 3480000, "max_q": 951.24},
                "GIULIANO": {"max_v": 94081021, "max_q": 101.0},
                "GANNANO": {"max_v": 2762000, "max_q": 99.0},
                "ACERENZA": {"max_v": 8887800, "max_q": 432.0},
                "GENZANO": {"max_v": 3100000, "max_q": 402.0}
            }

            nuovi_dati = []

            for name, info in info_invasi.items():
                diga_obj = [w for w in words if name in w['text'].upper()]
                if not diga_obj: continue
                
                target_y = diga_obj[0]['top']
                # Prendiamo parole a destra (x > 40% pagina) sulla stessa riga
                row_words = [w for w in words if abs(w['top'] - target_y) < 4 and w['x0'] > width * 0.4]
                row_words.sort(key=lambda x: x['x0'])
                
                numeri = [clean_numeric(w['text']) for w in row_words]
                # Rimuoviamo eventuali zeri spuri se la lista è troppo lunga
                numeri = [n for n in numeri if n != 0 or '0' in [w['text'] for w in row_words]]

                if len(numeri) >= 4:
                    try:
                        # --- LOGICA DI ASSEGNAZIONE PER RANGE ---
                        # 1. Quota attuale: il primo numero tra 50 e 1000
                        q_attuale = next((n for n in numeri if 50 <= n <= 1000), 0)
                        
                        # 2. Meteo: sempre gli ultimi due
                        pioggia = numeri[-2]
                        neve = numeri[-1]
                        
                        # 3. Volume Netto: il numero più grande tra quelli rimanenti
                        # Escludiamo quota e meteo
                        restanti = [n for n in numeri if n != q_attuale and n != pioggia and n != neve]
                        v_netto = max(restanti) if restanti else 0
                        
                        # 4. Trend: il numero che avanza tra quota e volume (spesso piccolo)
                        # Di solito è subito dopo q_attuale
                        idx_q = numeri.index(q_attuale)
                        trend = numeri[idx_q + 1] if len(numeri) > idx_q + 1 and numeri[idx_q+1] != v_netto else 0

                        d = {
                            "diga": name,
                            "quota_max_slm": info["max_q"],
                            "volume_max_lordo_mc": info["max_v"],
                            "quota_attuale_slm": q_attuale,
                            "trend_variazione_cm": trend,
                            "volume_netto_attuale_mc": v_netto,
                            "pioggia_mm": pioggia,
                            "neve_cm": neve,
                            "percentuale_riempimento": round((v_netto / info["max_v"] * 100), 2)
                        }
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
                print(f"Aggiornato con successo: {len(nuovi_dati)} dighe.")

    except Exception as e: print(f"Errore: {e}")

if __name__ == "__main__":
    scrape_bollettino()
