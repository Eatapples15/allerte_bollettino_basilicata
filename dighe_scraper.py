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
        # Cerchiamo il link al PDF più recente
        match_pdf = re.findall(r'href="(.*?Bollettino_(\d{4}-\d{2}-\d{2})\.pdf)"', resp.text)
        if not match_pdf: return print("Nessun PDF trovato.")
        
        pdf_url, data_bollettino = match_pdf[-1]
        print(f"Analisi PDF del {data_bollettino}")
        
        pdf_res = requests.get(pdf_url, headers=headers)
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            text = pdf.pages[0].extract_text()
            lines = text.split('\n')
            
            nuovi_dati = []
            # Lista dighe con i loro volumi massimi teorici per calcolare la % se mancano dati
            target_dighe = {
                "COTUGNO": 480700000, "PERTUSILLO": 155000000, "CAMASTRA": 18418128,
                "BASENTELLO": 33039968, "CONZA": 61813380, "SAETTA": 3480000,
                "GIULIANO": 94081021, "GANNANO": 2762000, "ACERENZA": 8887800, "GENZANO": 3100000
            }

            for line in lines:
                line_u = line.upper()
                diga_nome = next((d for d in target_dighe.keys() if d in line_u), None)
                
                if diga_nome:
                    # Estraiamo TUTTI i numeri della riga
                    numeri = [clean_numeric(n) for n in re.findall(r'[\d\.,]+', line)]
                    # Rimuoviamo gli zeri iniziali che spesso sono residui di formattazione
                    numeri = [n for n in numeri if n != 0 or '0' in line]
                    
                    if len(numeri) < 4: continue

                    try:
                        # LOGICA DI ASSEGNAZIONE INTELLIGENTE
                        # La quota max è solitamente il primo numero < 2000
                        quota_max = numeri[0]
                        # Il volume lordo max è il numero più grande all'inizio
                        v_max_lordo = target_dighe[diga_nome]
                        
                        # Il volume NETTO attuale è l'ultimo numero molto grande (> 1000)
                        # prima dei dati meteo (che sono gli ultimi due)
                        volumi_grandi = [n for n in numeri if n > 1000]
                        v_netto_attuale = volumi_grandi[-1] if volumi_grandi else 0
                        
                        # La quota attuale è il numero < 2000 che precede il trend
                        # (solitamente a metà lista numeri)
                        quote = [n for n in numeri if 50 < n < 1500]
                        quota_attuale = quote[-1] if quote else 0
                        
                        # Trend e Meteo
                        trend = numeri[-3] if len(numeri) >= 9 else 0
                        pioggia = numeri[-2] if len(numeri) >= 2 else 0
                        neve = numeri[-1] if len(numeri) >= 1 else 0
                        
                        d = {
                            "diga": diga_nome,
                            "quota_max_slm": quota_max,
                            "volume_max_lordo_mc": v_max_lordo,
                            "quota_attuale_slm": quota_attuale,
                            "trend_variazione_cm": trend,
                            "volume_netto_attuale_mc": v_netto_attuale,
                            "pioggia_mm": pioggia,
                            "neve_cm": neve,
                            "percentuale_riempimento": round((v_netto_attuale / v_max_lordo * 100), 2) if v_max_lordo > 0 else 0
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
                print(f"Successo: {len(nuovi_dati)} dighe mappate.")

    except Exception as e: print(f"Errore: {e}")

if __name__ == "__main__":
    scrape_bollettino()
