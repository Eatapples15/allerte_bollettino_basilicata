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
        print(f"Analisi PDF: {pdf_url}")
        
        pdf_res = requests.get(pdf_url, headers=headers)
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            text = pdf.pages[0].extract_text()
            lines = text.split('\n')
            
            nuovi_dati = []
            # Database capacità massime per calcoli e validazione
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

            for line in lines:
                line_u = line.upper()
                diga_match = next((name for name in info_invasi if name in line_u), None)
                
                if diga_match:
                    # Estraiamo TUTTI i numeri presenti nella riga
                    numeri = [clean_numeric(n) for n in re.findall(r'[\d\.,]+', line)]
                    # Se la riga è povera di numeri, passiamo alla successiva
                    if len(numeri) < 5: continue

                    try:
                        # MAPPATURA INTELLIGENTE
                        # 1. Pioggia e Neve sono sempre gli ultimi due
                        pioggia = numeri[-2]
                        neve = numeri[-1]

                        # 2. Il volume netto attuale nel PDF 2026 è solitamente il numero 
                        # prima della pioggia (o penultimo dei volumi grandi)
                        volumi_grandi = [n for n in numeri if n > 1000 and n != info_invasi[diga_match]["max_v"]]
                        v_netto = volumi_grandi[-1] if volumi_grandi else 0

                        # 3. La quota attuale è un numero tra 50 e 1000, escludendo la quota max
                        quote_possibili = [n for n in numeri if 50 <= n <= 1000 and n != info_invasi[diga_match]["max_q"]]
                        q_attuale = quote_possibili[-1] if quote_possibili else 0

                        # 4. Il trend è solitamente tra la quota attuale e il volume
                        # Lo cerchiamo come numero piccolo (spesso < 100) vicino alla quota
                        trend = 0
                        if len(numeri) > 7:
                            # Cerchiamo un numero con segno o vicino alla posizione tipica (indice 7)
                            trend = numeri[7] if abs(numeri[7]) < 500 else 0

                        d = {
                            "diga": diga_match,
                            "quota_max_slm": info_invasi[diga_match]["max_q"],
                            "volume_max_lordo_mc": info_invasi[diga_match]["max_v"],
                            "quota_attuale_slm": q_attuale,
                            "trend_variazione_cm": trend,
                            "volume_netto_attuale_mc": v_netto,
                            "pioggia_mm": pioggia,
                            "neve_cm": neve,
                            "percentuale_riempimento": round((v_netto / info_invasi[diga_match]["max_v"] * 100), 2) if v_netto > 0 else 0
                        }
                        nuovi_dati.append(d)
                    except Exception as e:
                        print(f"Errore su {diga_match}: {e}")

            if nuovi_dati:
                # Caricamento e pulizia del file JSON esistente (rimozione date sporche)
                storico = {}
                if os.path.exists(FILE_JSON):
                    with open(FILE_JSON, 'r') as f:
                        try:
                            storico = json.load(f)
                            # Rimuoviamo chiavi non standard come "05-01-2026" se presenti
                            storico = {k: v for k, v in storico.items() if len(k) == 10 and k.startswith("20")}
                        except: storico = {}
                
                storico[data_bollettino] = {"scraped_at": datetime.now().isoformat(), "dati": nuovi_dati}
                
                with open(FILE_JSON, 'w') as f:
                    json.dump(storico, f, indent=4)
                print(f"Successo: {len(nuovi_dati)} dighe salvate.")

    except Exception as e: print(f"Errore: {e}")

if __name__ == "__main__":
    scrape_bollettino()
