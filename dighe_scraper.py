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
        if s.count('.') > 1: s = s.replace('.', '')
        if ',' in s: s = s.replace('.', '').replace(',', '.')
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
            words = page.extract_words(horizontal_ltr=True, x_tolerance=3, y_tolerance=3)
            
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
                # Cerchiamo la riga della diga
                diga_objs = [w for w in words if name in w['text'].upper()]
                if not diga_objs: continue
                
                target_y = diga_objs[0]['top']
                # Prendiamo TUTTA la riga per catturare tutti i numeri
                row_words = [w for w in words if abs(w['top'] - target_y) < 8]
                row_words.sort(key=lambda x: x['x0'])
                
                # Ricostruzione token
                tokens = []
                if row_words:
                    current = row_words[0]['text']
                    for i in range(1, len(row_words)):
                        if row_words[i]['x0'] - row_words[i-1]['x1'] < 5 or current.endswith('.'):
                            current += row_words[i]['text']
                        else:
                            tokens.append(current)
                            current = row_words[i]['text']
                    tokens.append(current)

                numeri = [clean_numeric(t) for t in tokens if (clean_numeric(t) != 0 or '0' in t) and not any(c.isalpha() for c in t)]
                
                # Dal tuo debug abbiamo visto che i dati 2026 sono sempre nelle posizioni finali
                # Ordine tipico: [V_Max, Q_Max, ... , Q_Oggi, Trend, V_Lordo_Oggi, V_Netto_Oggi, Pioggia, Neve]
                if len(numeri) >= 8:
                    try:
                        pioggia = numeri[-2]
                        neve = numeri[-1]
                        v_netto = numeri[-3]
                        trend = numeri[-5] # Il trend è solitamente 2 posizioni prima del netto
                        q_attuale = numeri[-6] # La quota è solitamente prima del trend

                        # Validazione quote (devono essere sensate)
                        if not (50 <= q_attuale <= 1000):
                            # Se la posizione -6 fallisce, cerchiamo il primo numero "quota" da destra
                            for n in reversed(numeri[:-3]):
                                if 50 <= n <= 1000:
                                    q_attuale = n
                                    break

                        nuovi_dati.append({
                            "diga": name,
                            "quota_max_slm": info["max_q"],
                            "volume_max_lordo_mc": info["max_v"],
                            "quota_attuale_slm": q_attuale,
                            "trend_variazione_cm": trend if abs(trend) < 500 else 0, # Protezione contro volumi scambiati per trend
                            "volume_netto_attuale_mc": v_netto,
                            "pioggia_mm": pioggia,
                            "neve_cm": neve,
                            "percentuale_riempimento": round((v_netto / info["max_v"] * 100), 2)
                        })
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
