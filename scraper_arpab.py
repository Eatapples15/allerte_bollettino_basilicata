import requests
import json
import os
import time
from datetime import datetime

class ArpabFullScraper:
    def __init__(self):
        self.base_url = "https://arpabaegis.arpab.it/Datascape/v3"
        # Usiamo una sessione per gestire i cookie automaticamente
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://arpabaegis.arpab.it/', # Fondamentale: dice al server che arrivi dal sito ufficiale
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://arpabaegis.arpab.it'
        }
        self.output_dir = "data"
        self.output_file = os.path.join(self.output_dir, "arpab_all_stations.json")

    def init_session(self):
        """Visita la home page per ottenere i cookie di sessione necessari."""
        try:
            self.session.get("https://arpabaegis.arpab.it/", headers=self.headers, timeout=15)
            return True
        except Exception as e:
            print(f"Errore inizializzazione sessione: {e}")
            return False

    def get_all_stations(self):
        url = f"{self.base_url}/stations"
        params = {
            'category': '1',
            'ui_culture': 'it'
        }
        try:
            # Usiamo self.session invece di requests
            response = self.session.get(url, params=params, headers=self.headers, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Errore critico nel recupero lista stazioni: {e}")
            return []

    def get_station_details(self, station_id):
        url = f"{self.base_url}/elements"
        params = {
            'station_id': station_id,
            'category': '1',
            'ui_culture': 'it',
            'field': ['ElementName', 'Time', 'Value', 'Decimals', 'MeasUnit', 'Trend', 'StateId'],
            '_': int(time.time() * 1000)
        }
        try:
            response = self.session.get(url, params=params, headers=self.headers, timeout=15)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

    def run(self):
        # 0. Inizializza
        if not self.init_session():
            print("Impossibile stabilire una sessione. Esco.")
            return

        # 1. Trova tutte le stazioni
        stations_list = self.get_all_stations()
        if not stations_list:
            print("Nessuna stazione trovata o accesso negato (401).")
            return

        print(f"Trovate {len(stations_list)} stazioni. Inizio scaricamento dettagli...")
        
        all_results = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_stations": len(stations_list),
            "stations": []
        }

        for i, st in enumerate(stations_list):
            s_id = st.get('StationId') or st.get('id')
            s_name = st.get('StationName') or st.get('name', 'Ignoto')
            print(f"[{i+1}/{len(stations_list)}] Recupero dati per: {s_name} (ID: {s_id})")
            
            details = self.get_station_details(s_id)
            all_results["stations"].append({
                "metadata": st,
                "sensors": details if details else []
            })
            time.sleep(0.5)

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=4, ensure_ascii=False)
        
        print(f"\nOperazione completata! File salvato: {self.output_file}")

if __name__ == "__main__":
    scraper = ArpabFullScraper()
    scraper.run()
