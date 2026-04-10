import requests
import json
import os
import time
from datetime import datetime

class ArpabFullScraper:
    def __init__(self):
        self.base_url = "https://arpabaegis.arpab.it/Datascape/v3"
        self.session = requests.Session()
        
        # Header ultra-realistici
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://arpabaegis.arpab.it/Datascape/v3/view/index.html?ui_culture=it',
            'Origin': 'https://arpabaegis.arpab.it',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
        self.output_dir = "data"
        self.output_file = os.path.join(self.output_dir, "arpab_all_stations.json")

    def init_session(self):
        """Simula l'ingresso nel portale per raccogliere i cookie di sicurezza."""
        try:
            # Carichiamo la pagina che ospita la mappa
            main_page = "https://arpabaegis.arpab.it/Datascape/v3/view/index.html?ui_culture=it"
            response = self.session.get(main_page, headers=self.headers, timeout=20)
            
            # Piccolo trucco: il server potrebbe aver bisogno di un istante per registrare la sessione
            time.sleep(2)
            
            # Copiamo i cookie ottenuti nella sessione per le chiamate successive
            self.session.cookies.update(response.cookies)
            return True
        except Exception as e:
            print(f"Errore inizializzazione: {e}")
            return False

    def get_all_stations(self):
        url = f"{self.base_url}/stations"
        # Aggiungiamo il timestamp casuale che usano loro per evitare cache
        params = {
            'category': '1',
            'ui_culture': 'it',
            '_': int(time.time() * 1000)
        }
        try:
            response = self.session.get(url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code == 401:
                print("DEBUG: Il server richiede ancora un'autorizzazione specifica.")
                return []
                
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Errore critico lista stazioni: {e}")
            return []

    def get_station_details(self, station_id):
        url = f"{self.base_url}/elements"
        params = {
            'station_id': station_id,
            'category': '1',
            'ui_culture': 'it',
            'field': ['ElementName', 'Time', 'Value', 'Decimals', 'MeasUnit', 'Trend', 'StateId', 'IsQueryable'],
            '_': int(time.time() * 1000)
        }
        try:
            response = self.session.get(url, params=params, headers=self.headers, timeout=20)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

    def run(self):
        if not self.init_session():
            return

        stations_list = self.get_all_stations()
        if not stations_list:
            print("Accesso negato o lista vuota. Tentativo di fallback...")
            return

        print(f"Successo! Recupero dati per {len(stations_list)} stazioni.")
        
        all_results = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stations": []
        }

        for st in stations_list:
            s_id = st.get('StationId')
            s_name = st.get('StationName', 'Unknown')
            print(f"Scarico: {s_name}...")
            
            details = self.get_station_details(s_id)
            all_results["stations"].append({
                "info": st,
                "data": details if details else []
            })
            time.sleep(0.5)

        os.makedirs(self.output_dir, exist_ok=True)
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=4, ensure_ascii=False)
        print("Salvataggio completato.")

if __name__ == "__main__":
    ArpabFullScraper().run()
