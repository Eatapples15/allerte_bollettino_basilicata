import requests
from bs4 import BeautifulSoup
import pdfplumber
import io
import json
import os
import re
from datetime import datetime

FILE_JSON = "storico_invasi.json"

def clean_numeric(value):
    if value is None: return 0.0
    # Rimuove tutto tranne numeri, virgole e punti
    s = str(value).replace(' ', '').strip()
    s = re.sub(r'[^\d,.-]', '', s)
    if not s or s == '-': return 0.0
    try:
        if ',' in s and '.' in s: s = s.replace('.', '').replace(',', '.')
        elif ',' in s: s = s.replace(',', '.')
        return float(s)
    except: return 0.0

def scrape_bollettino():
    # --- Gestione URL (Mese corrente) ---
    mesi = {1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 6: "giugno",
            7: "luglio", 8: "agosto", 9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"}
    ora = datetime.now()
    url_pagina = f"https://acquedelsudspa.it/servizi/{mesi[ora.month]}-{ora.year}/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url_pagina, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if 'Bollettino' in a['href'] and '.pdf' in a['href']]
        
        if not links: return print("Nessun bollettino trovato.")
        
        ultimo_pdf_url = links[-1]
        data_match = re.search(r'(\d{2}-\w+-\d{4})', ultimo_pdf_url)
        data_bollettino = data_match.group(1) if data_match else ora.strftime("%d-%m-%Y")
        
        print(f"Analisi PDF: {ultimo_pdf_url}")
        pdf_res = requests.get(ultimo_pdf_url, headers=headers)
        
        with pdfplumber.open(io.BytesIO(pdf_res.content)) as pdf:
            page = pdf.pages[0]
            # Estraiamo la tabella senza forzare le linee, per evitare celle fuse male
            table = page.extract_table()
            
            if not table: return

            nuovi_dati = []
            for row in table:
                # 1. Pulizia riga: rimuoviamo i None e gli spazi
                row = [c.strip() if c else "" for c in row]
                
                # 2. Identificazione Diga
                if not row[0] or any(x in row[0].upper() for x in ["DESCRIZIONE", "INVASI", "DIGA", "TOTALE"]):
                    continue
                
                nome_diga = row[0].split('\n')[0].upper()
                
                # 3. Estrazione dinamica: prendiamo TUTTI i numeri presenti nella riga
                numeri_riga = []
                for cell in row[1:]:
                    # Se la cella contiene più righe (testo a capo), le dividiamo
                    parti = cell.split('\n')
                    for p in parti:
                        val = clean_numeric(p)
                        if val != 0.0 or p == '0': # Teniamo anche lo zero se è esplicito
                            numeri_riga.append(val)
                
                # DEBUG: stampiamo cosa vede lo script per Camastra
                if "CAMASTRA" in nome_diga:
                    print(f"Diga: {nome_diga} | Numeri trovati: {numeri_riga}")

                # 4. Assegnazione basata sulla struttura tipica (11-12 numeri totali)
                # Struttura attesa: [Q_Max, V_Lordo_Max, Q_2024, V_Lordo_2024, V_Netto_2024, Q_Attuale, Trend, V_Lordo_Attuale, V_Netto_Attuale, Pioggia, Neve]
                if len(numeri_riga) >= 9:
                    try:
                        # Usiamo indici negativi per pioggia e neve (sono sempre alla fine)
                        pioggia = numeri_riga[-2]
                        neve = numeri_riga[-1]
                        
                        # Il volume netto attuale è solitamente il terzultimo o quartultimo numero grande
                        # Cerchiamo il volume netto attuale (indice 8 se la riga è completa di 11 elementi)
                        # In una riga standard da 11/12 elementi:
                        # 0: Q_Max, 1: V_L_Max, 5: Q_Attuale, 6: Trend, 8: V_N_Attuale
                        v_netto = numeri_riga[8] if len(numeri_riga) > 8 else numeri_riga[-3]
                        v_max_lordo = numeri_riga[1]
                        q_attuale = numeri_riga[5] if len(numeri_riga) > 5 else 0
                        trend = numeri_riga[6] if len(numeri_riga) > 6 else 0
                        q_max = numeri_riga[0]

                        d = {
                            "diga": nome_diga,
                            "quota_max_slm": q_max,
                            "volume_max_lordo_mc": v_max_lordo,
                            "quota_attuale_slm": q_attuale,
                            "trend_variazione_cm": trend,
                            "volume_netto_attuale_mc": v_netto,
                            "pioggia_mm": pioggia,
                            "neve_cm": neve,
                            "percentuale_riempimento": round((v_netto / v_max_lordo * 100), 2) if v_max_lordo > 0 else 0
                        }
                        nuovi_dati.append(d)
                    except Exception as e:
                        print(f"Errore assegnazione {nome_diga}: {e}")

            # --- Salvataggio ---
            storico = {}
            if os.path.exists(FILE_JSON):
                with open(FILE_JSON, 'r', encoding='utf-8') as f:
                    try: storico = json.load(f)
                    except: storico = {}
            
            storico[data_bollettino] = {"scraped_at": datetime.now().isoformat(), "dati": nuovi_dati}
            with open(FILE_JSON, 'w', encoding='utf-8') as f:
                json.dump(storico, f, indent=4, ensure_ascii=False)
            
            print(f"Aggiornato bollettino {data_bollettino}. Trovate {len(nuovi_dati)} dighe.")

    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    scrape_bollettino()
