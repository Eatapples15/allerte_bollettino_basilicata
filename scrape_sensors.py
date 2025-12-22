import requests
import json
import datetime
import re
import sys

# CONFIGURAZIONE URL
BASE_URL = "https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php"
JSON_FILENAME = "dati_sensori.json"

SENSORI = {
    "idrometria": {"code": "I", "label": "Idrometri", "unit": "m", "threshold": 2.0},
    "pluviometria": {"code": "P", "label": "Pluviometri", "unit": "mm", "threshold": 40.0},
    "anemometria": {"code": "VV", "label": "Anemometri", "unit": "m/s", "threshold": 15.0},
    "termometria": {"code": "T", "label": "Termometri", "unit": "°C", "threshold": 38.0},
    "nivometria": {"code": "N", "label": "Nivometri", "unit": "cm", "threshold": 5.0}
}

FAKE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def clean_html_tag(raw_html):
    # Rimuove i tag HTML lasciando solo il testo
    clean = re.sub('<.*?>', '', raw_html)
    return clean.strip()

def scrape_sensor_regex(sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"\n--- Regex Analisi {config['label']} ({url}) ---")
    
    data_list = []
    
    try:
        r = requests.get(url, headers=FAKE_HEADERS, timeout=30)
        html_content = r.text
        
        # DEBUG: Stampiamo i primi 500 caratteri per vedere cosa scarica
        print(f"Bytes scaricati: {len(html_content)}")
        
        # PATTERN REGEX PER TROVARE LE RIGHE DELLA TABELLA
        # Cerca:
        # 1. Una cella con un link (Nome Stazione + ID)
        # 2. Una cella con data (dd/mm/yyyy hh:mm)
        # 3. Una cella con un numero (Valore)
        
        # Pattern spiegato:
        # <td.*?>.*?<a href="stazione\.php\?id=(\d+)".*?>(.*?)<\/a>.*?<\/td>  --> Cattura ID e Nome
        # \s*<td.*?>(.*?)<\/td>  --> Cattura Data
        # \s*<td.*?>(.*?)<\/td>  --> Cattura Valore
        
        pattern = r'<td[^>]*>.*?<a href="stazione\.php\?id=(\d+)"[^>]*>(.*?)<\/a>.*?<\/td>\s*<td[^>]*>(.*?)<\/td>\s*<td[^>]*>(.*?)<\/td>'
        
        matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
        print(f"🔍 Pattern trovati: {len(matches)}")

        for match in matches:
            station_id = match[0].strip()
            nome_stazione = clean_html_tag(match[1])
            data_ora = clean_html_tag(match[2])
            valore_raw = clean_html_tag(match[3])
            
            # Filtri di validità
            if not nome_stazione or "Stazione" in nome_stazione: continue
            
            # Parsing valore numerico
            try:
                clean_val = valore_raw.replace(",", ".").strip()
                match_num = re.search(r'-?\d+(\.\d+)?', clean_val)
                if not match_num: continue
                valore_num = float(match_num.group(0))
            except: continue

            status = "normal"
            if abs(valore_num) >= config['threshold']: status = "alert"
            
            data_list.append({
                "id": station_id,
                "nome": nome_stazione,
                "data": data_ora,
                "valore": valore_num,
                "status": status
            })

    except Exception as e:
        print(f"❌ Errore Regex: {e}")

    print(f"✅ Record estratti: {len(data_list)}")
    return data_list

def main():
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    total = 0
    for key, config in SENSORI.items():
        readings = scrape_sensor_regex(key, config)
        final_data["sensori"][key] = { "meta": config, "dati": readings }
        total += len(readings)

    try:
        with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Salvataggio completato ({total} sensori)")
    except Exception as e: print(f"Errore file: {e}")

if __name__ == "__main__":
    main()
