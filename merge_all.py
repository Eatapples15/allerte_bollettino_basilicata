import json
import os
import re
import requests

# Configurazione file
GEO_COMUNI = 'limits_R_17_municipalities.geojson'
DATA_FILE = 'dati_bollettino.json'
# URL Corretto per i confini delle zone di allerta (Dipartimento Nazionale)
ZONE_GEO_URL = "https://raw.githubusercontent.com/pcm-dpc/DPC-Mappe/main/allertamento/gu_zone/geojson/gu_zone.json"

OUT_COMUNI = 'bollettino_comunale_live.geojson'
OUT_ZONE = 'bollettino_zone_live.geojson'

# Mappatura fornita dall'utente (Normalizzata automaticamente dallo script)
USER_MAP_INPUT = {
    "BASI A1": "Atella, Barile, Filiano, Forenza, Ginestra, Lavello, Melfi, Montemilone, Palazzo S.G., Pescopagano, Rapolla, Rapone, Rionero in Vulture, Ripacandida, Ruvo del Monte, S. Fele, Venosa",
    "BASI A2": "Balvano, Baragiano, Bella, Brienza, Castelgrande, Muro Lucano, Picerno, Ruoti, S. Angelo le Fratte, Sasso di Castalda, Satriano di Lucania, Savoia di Lucania, Vietri di Potenza, Tito",
    "BASI B": "Abriola, Accettura, Acerenza, Albano di Lucania, Anzi, Avigliano, Banzi, Brindisi Montagna, Calciano, Calvello, Campomaggiore, Cancellara, Castelmezzano, Garaguso, Genzano di Lucania, Grassano, Grottole, Irsina, Laurenzana, Matera, Miglionico, Oliveto Lucano, Oppido Lucano, Pietragalla, Pietrapertosa, Pignola, Pomarico, Potenza, Salandra, S. Chirico Nuovo, S. Mauro Forte, Tolve, Tricarico, Trivigno, Vaglio Basilicata, Ferrandina",
    "BASI C": "Aliano, Armento, Calvera, Carbone, Castronuovo S. Andrea, Cersosimo, Chiaromonte, Cirigliano, Colobraro, Corleto Perticara, Episcopia, Fardella, Francavilla in Sinni, Gallicchio, Gorgoglione, Grumento Nova, Guardia Perticara, Marsico Nuovo, Marsicovetere, Missanello, Moliterno, Montemurror, Noepoli, Paterno, Roccanova, S. Chirico Raparo, S. Costantino Albanese, S. Giorgio Lucano, S. Martino d'Agri, S. Paolo Albanese, S. Severino Lucano, Sant'Arcangelo, Sarconi, Senise, Spinoso, Stigliano, Teana, Terranova di Pollino, Tramutola, Viggiano, Valsinni",
    "BASI D": "Castelluccio Inferiore, Castelluccio Superiore, Castelsaraceno, Lagonegro, Latronico, Lauria, Maratea, Nemoli, Rivello, Rotonda, Trecchina, Viggianello",
    "BASI E1": "Craco, Montalbano Jonico, Nova Siri, Policoro, Rotondella, Scanzano Jonico, Tursi",
    "BASI E2": "Bernalda, Ferrandina, Montescaglioso, Pisticci, Pomarico"
}

COLOR_MAP = {"green": "#00ff00", "yellow": "#ffff00", "orange": "#ff9900", "red": "#ff0000"}

def clean_string(s):
    if not s: return ""
    s = s.upper()
    # Converte S. o S in SAN per uniformare (es. S. Fele -> SAN FELE)
    s = s.replace("S. ", "SAN ").replace("S.", "SAN ").replace("S ", "SAN ")
    # Rimuove punteggiatura e spazi
    return re.sub(r'[^A-Z0-9]', '', s)

def merge_all():
    # Caricamento bollettino
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        alert_data = json.load(f)
    zone_alerts = alert_data.get('zone', {})

    # Invertiamo la mappa dell'utente per il lookup: Comune -> Zona
    comune_to_zona = {}
    for zona, comuni_str in USER_MAP_INPUT.items():
        for c in comuni_str.split(","):
            comune_to_zona[clean_string(c)] = zona

    # --- 1. COMUNI ---
    if os.path.exists(GEO_COMUNI):
        with open(GEO_COMUNI, 'r', encoding='utf-8') as f:
            com_geo = json.load(f)
        for feature in com_geo['features']:
            nome_geo = feature['properties'].get('name', '')
            zona_id = comune_to_zona.get(clean_string(nome_geo))
            if zona_id:
                info = zone_alerts.get(zona_id)
                col = info.get('oggi', 'green').lower() if info else 'green'
                feature['properties'].update({
                    'allerta_oggi': col, 'colore_web': COLOR_MAP.get(col, "#00ff00"),
                    'zona_nome': zona_id, 'rischio': info.get('rischio_oggi', '') if info else ''
                })
        with open(OUT_COMUNI, 'w', encoding='utf-8') as f:
            json.dump(com_geo, f, ensure_ascii=False)
        print("Mappa comuni aggiornata.")

    # --- 2. ZONE (Confini spessi) ---
    try:
        r = requests.get(ZONE_GEO_URL)
        r.raise_for_status()
        res = r.json()
        basi_zones = []
        for f in res['features']:
            sigla = f['properties'].get('Sigla') or f['properties'].get('SIGLA')
            if sigla and sigla.startswith('BASI'):
                # DPC usa BASI-A1, noi BASI A1
                nome_z = f['properties'].get('Nome_Zona', '').replace("-", " ")
                info = zone_alerts.get(nome_z)
                col = info.get('oggi', 'green').lower() if info else 'green'
                f['properties'].update({
                    'allerta_oggi': col, 'colore_web': COLOR_MAP.get(col, "#00ff00"),
                    'descrizione': info.get('rischio_oggi', '') if info else ''
                })
                basi_zones.append(f)
        if basi_zones:
            with open(OUT_ZONE, 'w', encoding='utf-8') as f:
                json.dump({"type": "FeatureCollection", "features": basi_zones}, f, ensure_ascii=False)
            print(f"Mappa zone aggiornata ({len(basi_zones)} zone).")
    except Exception as e:
        print(f"Errore download zone: {e}")

if __name__ == "__main__":
    merge_all()
