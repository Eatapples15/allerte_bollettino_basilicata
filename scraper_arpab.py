import json
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

class ArpabStealthScraper:
    def __init__(self):
        self.output_dir = "data"
        self.json_path = os.path.join(self.output_dir, "arpab_all_stations.json")
        self.log_path = os.path.join(self.output_dir, "last_run_status.txt")
        self.captured_data = {"stations_list": [], "details": []}

    def run(self):
        print(f"🚀 Avvio Scraper Stealth: {datetime.now()}")
        
        with sync_playwright() as p:
            # Configurazione Browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 720}
            )
            page = context.new_page()

            # Listener per intercettare il traffico di rete
            def handle_response(response):
                try:
                    if "stations" in response.url and response.status == 200:
                        self.captured_data["stations_list"] = response.json()
                        print(f"✅ Intercettate {len(self.captured_data['stations_list'])} stazioni.")
                    if "elements" in response.url and response.status == 200:
                        self.captured_data["details"].append(response.json())
                except:
                    pass

            page.on("response", handle_response)

            try:
                # 1. Carica il portale (timeout esteso a 60s per lentezza PA)
                print("📡 Accesso al portale ARPAB...")
                page.goto("https://arpabaegis.arpab.it/Datascape/v3/view/index.html?ui_culture=it", 
                          wait_until="networkidle", timeout=60000)
                
                # 2. Interazione simulata per attivare gli script
                page.mouse.wheel(0, 500)
                time.sleep(15) 

                # 3. Se mancano i dettagli, forziamo le chiamate API dal contesto browser
                if self.captured_data["stations_list"] and not self.captured_data["details"]:
                    print("🔄 Recupero forzato sensori (API Context)...")
                    for st in self.captured_data["stations_list"][:15]: # Limite prime 15 per evitare ban
                        s_id = st.get('StationId')
                        url = f"https://arpabaegis.arpab.it/Datascape/v3/elements?station_id={s_id}&category=1&ui_culture=it&field=ElementName&field=Time&field=Value&field=Decimals&field=MeasUnit&field=Trend&field=StateId&field=IsQueryable"
                        res = page.evaluate(f'fetch("{url}").then(r => r.ok ? r.json() : null)')
                        if res:
                            self.captured_data["details"].append({"station": st, "sensors": res})
                        time.sleep(1)

            except Exception as e:
                print(f"❌ Errore durante l'esecuzione: {e}")

            # 4. Salvataggio finale e gestione cartelle
            os.makedirs(self.output_dir, exist_ok=True)
            
            if self.captured_data["details"]:
                output = {
                    "last_updated": datetime.now().isoformat(),
                    "data": self.captured_data["details"]
                }
                with open(self.json_path, "w", encoding="utf-8") as f:
                    json.dump(output, f, indent=4, ensure_ascii=False)
                print(f"💾 File salvato con successo: {self.json_path}")
            else:
                with open(self.log_path, "w") as f:
                    f.write(f"Fallito il {datetime.now()}. Il server ha bloccato la richiesta (401/403).")
                print("⚠️ Dati non recuperati. Scritto file di log.")

            browser.close()

if __name__ == "__main__":
    ArpabStealthScraper().run()
