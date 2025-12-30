import json
import datetime
import re
import requests
from bs4 import BeautifulSoup

JSON_FILENAME = "dati_sensori.json"
ANAGRAFICA_URL = "https://raw.githubusercontent.com/Eatapples15/allerte_bollettino_basilicata/main/anagrafica_stazioni.json"
# URL diretto che restituisce la tabella completa
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"

SENSORI = {
    "pluviometria": "P",
    "anemometria": "VV",
    "idrometria": "I",
    "termometria": "T"
}

def super_clean(text):
    if not text: return ""
    t = text.upper()
    t = re.sub(r'\b(A|IN|PRESSO|FIUME|TORRENTE|CANALE|S\.|SAN|SS\d+)\b', '', t)
    t = re.sub(r'[^A-Z0-9]', '', t)
    return t.strip()

def scrape():
    # 1. Carico Anagrafica
    try:
        r_ana = requests.get(ANAGRAFICA_URL)
        anagrafica_raw = r_ana.json()
    except:
        print("Errore anagrafica")
        return

    stazioni_finali = {}

    # 2. Ciclo sui sensori con richieste dirette (No Selenium!)
    for cat, code in SENSORI.items():
        try:
            print(f"Lettura dati {cat}...")
            # Questa chiamata simula la scelta del sensore e forza la visualizzazione di 500 righe
            response = requests.post(BASE_URL, data={'st': code}, timeout=20)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            rows = soup.find_all("tr")
            print(f"Trovate {len(rows)} righe per {code}")

            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 4: continue
                
                raw_name = cols[0].get_text(strip=True)
                valore = cols[3].get_text(strip=True)
                
                if not raw_name or valore in ["", "-", "n.d."]: continue

                # Identificazione stazione
                found_id = None
                id_match = re.search(r'\((\d+)\)', raw_name)
                if id_match: found_id = id_match.group(1)
                
                norm_site = super_clean(raw_name)
                if not found_id:
                    for a in anagrafica_raw:
                        if super_clean(a.get('stazione','')) in norm_site:
                            found_id = str(a['id'])
                            break

                s_key = found_id if found_id else f"UNKNOWN_{norm_site}"

                if s_key not in stazioni_finali:
                    geo = next((a for a in anagrafica_raw if str(a['id']) == found_id), None)
                    stazioni_finali[s_key] = {
                        "id": found_id,
                        "nome": raw_name.split('(')[0].strip().upper(),
                        "lat": geo['lat'] if geo else None,
                        "lon": geo['lon'] if geo else None,
                        "dati": {"pioggia": {}, "idro": None, "temp": None, "vento": None}
                    }

                st = stazioni_finali[s_key]
                low = raw_name.lower()
                if code == "P":
                    if "1 ora" in low or "1h" in low: st["dati"]["pioggia"]["h1"] = valore
                    elif "24 ore" in low or "24h" in low: st["dati"]["pioggia"]["h24"] = valore
                elif code == "I": st["dati"]["idro"] = valore
                elif code == "T": st["dati"]["temp"] = valore
                elif code == "VV": st["dati"]["vento"] = valore

        except Exception as e:
            print(f"Salto {cat} per errore: {e}")

    # 3. Salvataggio
    output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "stazioni": list(stazioni_finali.values())
    }

    with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    
    print(f"Fine! Totale stazioni salvate: {len(stazioni_finali)}")

if __name__ == "__main__":
    scrape()
