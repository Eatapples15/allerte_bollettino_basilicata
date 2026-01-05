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
    # Rimuove tutto tranne numeri, virgole e punti
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
            
            # Database info statiche per confronto e nomi completi
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
                # Cerchiamo la parola che contiene il nome della diga
                diga_objs = [w for w in words if name in w['text'].upper()]
                if not diga_objs: continue
                
                # Prendiamo la prima occorrenza (la riga della tabella)
                target_y = diga_objs[0]['top']
                
                # Estraiamo tutti i numeri sulla destra (dopo il 35% della larghezza)
                # Aumentiamo la tolleranza verticale a 5px per catturare righe leggermente disallineate
                row_words = [w for w in words if abs(w['top'] - target_y) < 5 and w['x0'] > width * 0.35]
                row_words.sort(key=lambda x: x['x0'])
                
                # Lista di tutti i numeri trovati nella riga
                numeri = []
                for w in row_words:
                    val = clean_numeric(w['text'])
                    # Accettiamo il valore se è un numero valido
                    if val != 0.0 or '0' in w['text']:
                        numeri.append(val)

                if len(numeri) >= 4:
                    try:
                        # --- ASSEGNAZIONE INTELLIGENTE BASATA SUI VALORI ---
                        
                        # 1. Quota Attuale: Il primo numero che cade nel range logico delle quote
                        # Escludiamo eventuali piccoli numeri residui del 2024
                        q_attuale = 0
                        for n in numeri:
                            if 50 <= n <= 1000 and n != info["max_q"]:
                                q_attuale = n
                                break
                        
                        # 2. Meteo: Sono gli ultimi due numeri della riga
                        pioggia = numeri[-2]
                        neve = numeri[-1]
                        
                        # 3. Volume Netto: Il numero più grande tra quelli che rimangono
                        # (Tipicamente espresso in mc, quindi migliaia o milioni)
                        possibili_volumi = [n for n in numeri if n > 1000 and n != info["max_v"] and n != q_attuale]
                        v_netto = possibili_volumi[-1] if possibili_volumi else 0
                        
                        # 4. Trend: È il numero che sta tra la quota attuale e i volumi
                        # Se non lo troviamo con certezza, lo mettiamo a 0
                        trend = 0
                        try:
                            idx_q = numeri.index(q_attuale)
                            potential_trend = numeri[idx_q + 1]
                            if abs(potential_trend) < 500 and potential_trend != v_netto:
                                trend = potential_trend
                        except:
                            trend = 0

                        d = {
                            "diga": name,
                            "quota_max_slm": info["max_q"],
                            "volume_max_lordo_mc": info["max_v"],
                            "quota_attuale_slm": q_attuale,
                            "trend_variazione_cm": trend,
                            "volume_netto_attuale_mc": v_netto,
                            "pioggia_mm": pioggia,
                            "neve_cm": neve,
                            "percentuale_riempimento": round((v_netto / info["max_v"] * 100), 2) if v_netto > 0 else 0
                        }
                        nuovi_dati.append(d)
                        print(f"Mappata diga: {name} | Netto: {v_netto}")
                    except Exception as e:
                        print(f"Errore su {name}: {e}")

            if nuovi_dati:
                storico = {}
                if os.path.exists(FILE_JSON):
                    with open(FILE_JSON, 'r') as f:
                        try: storico = json.load(f)
                        except: storico = {}
                
                storico[data_bollettino] = {"scraped_at": datetime.now().isoformat(), "dati": nuovi_dati}
                with open(FILE_JSON, 'w') as f:
                    json.dump(storico, f, indent=4)
                print(f"Fine. Totale dighe salvate: {len(nuovi_dati)}")

    except Exception as e:
        print(f"Errore generale: {e}")

if __name__ == "__main__":
    scrape_bollettino()
