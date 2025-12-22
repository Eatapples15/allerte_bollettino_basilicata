import json
import datetime
import re
import time
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

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

def clean_text(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', text.replace("\xa0", " ")).strip()

def parse_value(val_str):
    try:
        if not val_str: return None
        clean = re.sub(r'[^\d\.,\-]', '', val_str).replace(",", ".")
        match = re.search(r'-?\d+(\.\d+)?', clean)
        return float(match.group(0)) if match else None
    except:
        return None

def setup_driver():
    """Configura Chrome Headless per GitHub Actions"""
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Esegue senza interfaccia grafica
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # User agent reale per non essere bloccati
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def scrape_with_selenium(driver, sensor_key, config):
    url = f"{BASE_URL}?st={config['code']}"
    print(f"\n--- Navigazione verso {config['label']} ({url}) ---")
    
    data_list = []
    
    try:
        driver.get(url)
        # ASPETTA CHE IL JAVASCRIPT CARICHI LA TABELLA (5 secondi)
        time.sleep(5)
        
        # Prendi l'HTML generato dopo l'esecuzione del JS
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Cerca la tabella 'rilevazioni' o qualsiasi riga
        all_rows = soup.find_all("tr")
        print(f"🔎 Righe HTML trovate (post-JS): {len(all_rows)}")

        for row in all_rows:
            cols = row.find_all("td")
            if len(cols) < 4: continue # Servono almeno 4 colonne
            
            # Analisi colonne (Stazione, Comune, ..., Valore, Data)
            # La struttura visiva è solitamente: 
            # Col 0: Stazione (Link)
            # Col 3: Valore
            # Col 4: Data
            
            raw_cols = [clean_text(c.text) for c in cols]
            
            nome_stazione = raw_cols[0]
            if not nome_stazione or "Stazione" in nome_stazione: continue
            
            # Prova a leggere valore e data dalle colonne tipiche
            # A volte variano, cerchiamo la colonna col numero e quella con la data
            valore_num = None
            data_ora = ""
            
            # Cerca il valore nella colonna 3 (indice 3)
            if len(raw_cols) > 3:
                valore_num = parse_value(raw_cols[3])
            
            # Cerca la data nella colonna 4 (indice 4)
            if len(raw_cols) > 4:
                data_ora = raw_cols[4]

            if valore_num is None: continue

            # Estrazione ID Stazione
            station_id = ""
            link = cols[0].find("a")
            if link and 'href' in link.attrs:
                match = re.search(r'id=(\d+)', link['href'])
                if match: station_id = match.group(1)

            # Fix orario breve "12:30" -> "22/12/2025 12:30"
            if len(data_ora) <= 5 and ":" in data_ora:
                today = datetime.datetime.now().strftime("%d/%m/%Y")
                data_ora = f"{today} {data_ora}"

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
        print(f"❌ Errore Selenium: {e}")

    print(f"✅ Record estratti: {len(data_list)}")
    return data_list

def main():
    driver = setup_driver()
    
    final_data = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    total = 0
    try:
        for key, config in SENSORI.items():
            readings = scrape_with_selenium(driver, key, config)
            final_data["sensori"][key] = { "meta": config, "dati": readings }
            total += len(readings)
    finally:
        driver.quit() # Chiudi il browser sempre

    try:
        with open(JSON_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Salvataggio completato ({total} sensori)")
    except Exception as e:
        print(f"❌ Errore scrittura file: {e}")

if __name__ == "__main__":
    main()
