import json
import datetime
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def main():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # Configurazione categorie: Chiave JSON -> Codice Sito Regione
    categorie = {
        "pluviometria": "P",
        "idrometria": "I",
        "termometria": "T",
        "anemometria": "VV",
        "nivometria": "N"
    }
    
    output = {
        "ultimo_aggiornamento": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "sensori": {}
    }

    for cat_name, code in categorie.items():
        print(f"Recupero dati live per: {cat_name}...")
        try:
            driver.get(f"https://centrofunzionale.regione.basilicata.it/it/sensoriTempoReale.php?st={code}")
            # Attesa per il caricamento della tabella dinamica
            time.sleep(5) 
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            table = soup.find("table")
            if not table:
                continue

            rows = table.find_all("tr")
            data_list = []

            for r in rows:
                tds = r.find_all("td")
                # La struttura tipica ha: Stazione (0), Ora (1), Valore (3)
                if len(tds) >= 4:
                    nome = tds[0].get_text(strip=True)
                    # Evitiamo di catturare i valori spuri come se fossero nomi
                    if not any(u in nome.lower() for u in ["mm", " m", "°c", "hpa"]):
                        try:
                            val_raw = tds[3].get_text(strip=True).replace(",", ".")
                            valore = float(val_raw)
                            data_list.append({
                                "nome": nome,
                                "valore": valore,
                                "ora": tds[1].get_text(strip=True)
                            })
                        except ValueError:
                            continue
            
            output["sensori"][cat_name] = data_list
            print(f"✅ {cat_name}: {len(data_list)} sensori letti.")

        except Exception as e:
            print(f"❌ Errore durante lo scraping di {cat_name}: {e}")

    # Salva il file JSON per i dati LIVE
    with open("dati_sensori.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    
    driver.quit()
    print("🏁 Scraping LIVE completato.")

if __name__ == "__main__":
    main()
