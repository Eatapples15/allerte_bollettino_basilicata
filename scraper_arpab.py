import json
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

def run_scraper():
    print(f"Avvio scraper: {datetime.now()}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Usiamo un profilo browser completo
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # Contenitori per i dati intercettati
        captured_data = {
            "stations": [],
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Funzione per intercettare le risposte del server
        def handle_response(response):
            if "Datascape/v3/stations" in response.url and response.status == 200:
                try:
                    stations = response.json()
                    captured_data["stations_list"] = stations
                    print(f"Intercettate {len(stations)} stazioni dalla rete.")
                except:
                    pass

        page.on("response", handle_response)

        print("Caricamento portale e intercettazione dati...")
        # Navighiamo direttamente alla mappa
        page.goto("https://arpabaegis.arpab.it/Datascape/v3/view/index.html?ui_culture=it", wait_until="networkidle")
        
        # Diamo tempo al sito di popolare la mappa (questo attiva le chiamate API)
        time.sleep(10)

        # Se l'intercettazione automatica non basta, forziamo il recupero via browser
        # ma gestendo l'errore se la risposta non è JSON
        if "stations_list" in captured_data:
            for st in captured_data["stations_list"]:
                s_id = st.get('StationId')
                s_name = st.get('StationName', 'Ignoto')
                print(f"Recupero dati per {s_name}...")
                
                # Chiamata agli elementi del sensore
                res = page.evaluate(f"""
                    fetch("https://arpabaegis.arpab.it/Datascape/v3/elements?station_id={s_id}&category=1&ui_culture=it&field=ElementName&field=Time&field=Value&field=Decimals&field=MeasUnit&field=Trend&field=StateId&field=IsQueryable")
                    .then(r => r.ok ? r.json() : null)
                """)
                
                if res:
                    captured_data["stations"].append({
                        "info": st,
                        "sensors": res
                    })
                time.sleep(0.5)

        # Pulizia e salvataggio
        if captured_data["stations"]:
            os.makedirs("data", exist_ok=True)
            with open("data/arpab_all_stations.json", "w", encoding="utf-8") as f:
                json.dump(captured_data, f, indent=4, ensure_ascii=False)
            print(f"Operazione completata! Salvate {len(captured_data['stations'])} stazioni.")
        else:
            print("Errore: non è stato possibile recuperare i dati. Il server blocca ancora la richiesta.")

        browser.close()

if __name__ == "__main__":
    run_scraper()
