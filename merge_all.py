import json
import os
import re
import requests

# Configurazione file
GEO_COMUNI = 'limits_R_17_municipalities.geojson'
DATA_FILE = 'dati_bollettino.json'
ZONE_GEO_URL = "https://raw.githubusercontent.com/pcm-dpc/DPC-Mappe/master/allertamento/geojson/it_allerta.json"

OUT_COMUNI = 'bollettino_comunale_live.geojson'
OUT_ZONE = 'bollettino_zone_live.geojson'

MUNICIPALITY_MAP = {"ABRIOLA": "BASI B", "ACCETTURA": "BASI B", "ACERENZA": "BASI B", "ALBANO DI LUCANIA": "BASI B", "ALIANO": "BASI C", "ANZI": "BASI B", "ARMENTO": "BASI C", "ATELLA": "BASI A1", "AVIGLIANO": "BASI B", "BALVANO": "BASI A2", "BANZI": "BASI B", "BARAGIANO": "BASI A2", "BARILE": "BASI A1", "BELLA": "BASI A2", "BERNALDA": "BASI E2", "BRIENZA": "BASI A2", "BRINDISI MONTAGNA": "BASI B", "CALCIANO": "BASI B", "CALVELLO": "BASI B", "CALVERA": "BASI C", "CAMPOMAGGIORE": "BASI B", "CANCELLARA": "BASI B", "CARBONE": "BASI C", "CASTELGRANDE": "BASI A2", "CASTELLUCCIO INFERIORE": "BASI D", "CASTELLUCCIO SUPERIORE": "BASI D", "CASTELMEZZANO": "BASI B", "CASTELSARACENO": "BASI D", "CASTRONUOVO DI SANT ANDREA": "BASI C", "CERSOSIMO": "BASI C", "CHIAROMONTE": "BASI C", "CIRIGLIANO": "BASI C", "COLOBRARO": "BASI C", "CORLETO PERTICARA": "BASI C", "CRACO": "BASI E1", "EPISCOPIA": "BASI C", "FARDELLA": "BASI C", "FERRANDINA": "BASI E2", "FILIANO": "BASI A1", "FORENZA": "BASI A1", "FRANCAVILLA IN SINNI": "BASI C", "GALLICCHIO": "BASI C", "GARAGUSO": "BASI B", "GENZANO DI LUCANIA": "BASI B", "GINESTRA": "BASI A1", "GORGOGLIONE": "BASI C", "GRASSANO": "BASI B", "GROTTOLE": "BASI B", "GRUMENTO NOVA": "BASI C", "GUARDIA PERTICARA": "BASI C", "IRSINA": "BASI B", "LAGONEGRO": "BASI D", "LATRONICO": "BASI D", "LAURENZANA": "BASI B", "LAURIA": "BASI D", "LAVELLO": "BASI A1", "MARATEA": "BASI D", "MARSICO NUOVO": "BASI C", "MARSICOVETERE": "BASI C", "MASCHITO": "BASI A1", "MATERA": "BASI B", "MELFI": "BASI A1", "MIGLIONICO": "BASI B", "MISSANELLO": "BASI C", "MOLITERNO": "BASI C", "MONTALBANO JONICO": "BASI E1", "MONTEMILONE": "BASI A1", "MONTEMURRO": "BASI C", "MONTESCAGLIOSO": "BASI E2", "MURO LUCANO": "BASI A2", "NEMOLI": "BASI D", "NOEPOLI": "BASI C", "NOVA SIRI": "BASI E1", "OLIVETO LUCANO": "BASI B", "OPPIDO LUCANO": "BASI B", "PALAZZO SAN GERVASIO": "BASI A1", "PATERNO": "BASI C", "PESCOPAGANO": "BASI A1", "PICERNO": "BASI A2", "PIETRAGALLA": "BASI B", "PIETRAPERTOSA": "BASI B", "PIGNOLA": "BASI B", "PISTICCI": "BASI E2", "POLICORO": "BASI E1", "POMARICO": "BASI B", "POTENZA": "BASI B", "RAPOLLA": "BASI A1", "RAPONE": "BASI A1", "RIONERO IN VULTURE": "BASI A1", "RIPACANDIDA": "BASI A1", "RIVELLO": "BASI D", "ROCCANOVA": "BASI C", "ROTONDA": "BASI D", "ROTONDELLA": "BASI E1", "RUOTI": "BASI A2", "RUVO DEL MONTE": "BASI A1", "SALANDRA": "BASI B", "SAN CHIRICO NUOVO": "BASI B", "SAN CHIRICO RAPARO": "BASI C", "SAN COSTANTINO ALBANESE": "BASI C", "SAN FELE": "BASI A1", "SAN GIORGIO LUCANO": "BASI C", "SAN MARTINO DAGRI": "BASI C", "SAN MAURO FORTE": "BASI B", "SAN PAOLO ALBANESE": "BASI C", "SAN SEVERINO LUCANO": "BASI C", "SANT ANGELO LE FRATTE": "BASI A2", "SANT ARCANGELO": "BASI C", "SARCONI": "BASI C", "SASSO DI CASTALDA": "BASI A2", "SATRIANO DI LUCANIA": "BASI A2", "SAVOIA DI LUCANIA": "BASI A2", "SCANZANO JONICO": "BASI E1", "SENISE": "BASI C", "SPINOSO": "BASI C", "STIGLIANO": "BASI C", "TEANA": "BASI C", "TERRANOVA DI POLLINO": "BASI C", "TITO": "BASI A2", "TOLVE": "BASI B", "TRAMUTOLA": "BASI C", "TRECCHINA": "BASI D", "TRICARICO": "BASI B", "TRIVIGNO": "BASI B", "TURSI": "BASI C", "VAGLIO BASILICATA": "BASI B", "VALSINNI": "BASI C", "VENOSA": "BASI A1", "VIETRI DI POTENZA": "BASI A2", "VIGGIANELLO": "BASI D", "VIGGIANO": "BASI C"}
COLOR_MAP = {"green": "#00ff00", "yellow": "#ffff00", "orange": "#ff9900", "red": "#ff0000"}

def clean_string(s):
    return re.sub(r'[^A-Z0-9]', '', s.upper())

def merge_all():
    if not os.path.exists(DATA_FILE): 
        print("Errore: dati_bollettino.json non trovato")
        return
    
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        alert_data = json.load(f)
    zone_alerts = alert_data.get('zone', {})

    # --- 1. PROCESSO COMUNI ---
    if os.path.exists(GEO_COMUNI):
        with open(GEO_COMUNI, 'r', encoding='utf-8') as f:
            geo_comuni_data = json.load(f)
        clean_map = {clean_string(k): v for k, v in MUNICIPALITY_MAP.items()}
        for feature in geo_comuni_data['features']:
            nome = feature['properties'].get('name', '')
            zona_id = clean_map.get(clean_string(nome))
            if zona_id:
                info = zone_alerts.get(zona_id)
                col = info.get('oggi', 'green').lower() if info else 'green'
                feature['properties'].update({
                    'allerta_oggi': col,
                    'colore_web': COLOR_MAP.get(col, "#00ff00"),
                    'zona_nome': zona_id,
                    'rischio': info.get('rischio_oggi', '') if info else ''
                })
        with open(OUT_COMUNI, 'w', encoding='utf-8') as f:
            json.dump(geo_comuni_data, f, ensure_ascii=False, indent=2)
        print("Comuni ok.")

    # --- 2. PROCESSO ZONE ---
    try:
        print("Scaricamento zone...")
        res = requests.get(ZONE_GEO_URL).json()
        basi_zones = []
        for f in res['features']:
            # Cerchiamo Sigla o SIGLA (il DPC a volte cambia maiuscole)
            sigla = f['properties'].get('Sigla') or f['properties'].get('SIGLA')
            if sigla and sigla.startswith('BASI'):
                # Normalizziamo il nome zona per il match con il tuo JSON
                nome_z = f['properties'].get('Nome_Zona', '').replace("-", " ")
                info = zone_alerts.get(nome_z)
                col = info.get('oggi', 'green').lower() if info else 'green'
                f['properties'].update({
                    'allerta_oggi': col,
                    'colore_web': COLOR_MAP.get(col, "#00ff00"),
                    'descrizione': info.get('rischio_oggi', '') if info else ''
                })
                basi_zones.append(f)
        
        if basi_zones:
            with open(OUT_ZONE, 'w', encoding='utf-8') as f:
                json.dump({"type": "FeatureCollection", "features": basi_zones}, f, ensure_ascii=False, indent=2)
            print(f"Zone ok ({len(basi_zones)} trovate).")
        else:
            print("ATTENZIONE: Nessuna zona BASI trovata nel file DPC!")
            
    except Exception as e:
        print(f"Errore critico zone: {e}")

if __name__ == "__main__":
    merge_all()
