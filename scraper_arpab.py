import json
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

def run_scraper():
    print(f"Avvio scraper con Playwright: {datetime.now()}")
    
    with sync_playwright() as p:
        # Avviamo il browser (Chromium)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # 1. Navighiamo sulla pagina principale per ottenere i permessi/cookie
        print("Apertura portale ARPAB...")
        page.goto("https://arpabaegis.arpab.it/Datascape/v3/view/index.html?ui_culture=it", wait_until="networkidle")
        time.sleep(5) # Attendiamo il caricamento completo della mappa

        # 2. Eseguiamo la chiamata API direttamente dal contesto del browser
        # Questo bypassa il 401 perché usa i token e i cookie già validati dal sito
        print("Recupero lista stazioni via browser context...")
        
        stations_script = """
            async () => {
                const response = await fetch("https://arpabaegis.arpab.it/Datascape/v3/stations?category=1&ui_culture=it");
                return await response.json();
            }
        """
        
        try:
            stations_list = page.evaluate(stations_script)
            print(f"Successo! Trovate {len(stations_list)} stazioni.")
        except Exception as e:
            print(f"Errore durante l'estrazione: {e}")
            browser.close()
            return

        all_data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stations": []
        }

        # 3. Cicliamo sulle stazioni per prendere i sensori
        for st in stations_list:
            s_id = st.get('StationId')
            s_name = st.get('StationName', 'Unknown')
            print(f"Scaricamento dettagli per: {s_name}")

            elements_script = f"""
                async () => {{
                    const url = "https://arpabaegis.arpab.it/Datascape/v3/elements?station_id={s_id}&category=1&ui_culture=it&field=ElementName&field=Time&field=Value&field=Decimals&field=MeasUnit&field=Trend&field=StateId&field=IsQueryable";
                    const response = await fetch(url);
                    return await response.json();
                }}
            """
            try:
                details = page.evaluate(elements_script)
                all_data["stations"].append({
                    "info": st,
                    "sensors": details
                })
            except:
                continue
            
            time.sleep(0.5)

        # 4. Salvataggio
        os.makedirs("data", exist_ok=True)
        with open("data/arpab_all_stations.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)
        
        print("Salvataggio completato correttamente.")
        browser.close()

if __name__ == "__main__":
    run_scraper()
