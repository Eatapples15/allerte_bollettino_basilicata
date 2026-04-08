from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import random
import uvicorn

# ==========================================
# CONFIGURAZIONE
# ==========================================
NEON_DB_URL = "postgresql://neondb_owner:npg_Z6SIDcCRoNl5@ep-ancient-bar-alzsh334-pooler.c-3.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

app = FastAPI(title="Motore Idrologico Invasi Basilicata", version="1.0")

# Abilitiamo il CORS: questo permette al tuo futuro sito su Aruba di interrogare l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione sostituiremo "*" con "https://iltuodominio.it"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    return psycopg2.connect(NEON_DB_URL, cursor_factory=RealDictCursor)

# ==========================================
# MODELLI DATI (Input dell'utente dal sito web)
# ==========================================
class ParametriSimulazione(BaseModel):
    nome_diga: str
    apertura_m3s: float  # Inserimento manuale in metri cubi al secondo
    giorni_previsione: int = 7

# ==========================================
# ENDPOINT (Le "porte" per il tuo sito Aruba)
# ==========================================

@app.get("/api/stato-attuale")
def get_stato_dighe():
    """Restituisce l'ultimissimo dato di volume e quota per tutte le dighe."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Query SQL avanzata per prendere solo la riga più recente per ogni diga
        query = """
            SELECT nome_diga, volume_mm3, quota_mslm, data_rilevazione
            FROM (
                SELECT *, ROW_NUMBER() OVER(PARTITION BY nome_diga ORDER BY data_rilevazione DESC) as rn
                FROM storico_invasi
            ) sub
            WHERE rn = 1;
        """
        cursor.execute(query)
        dati_attuali = cursor.fetchall()
        return {"status": "success", "dati": dati_attuali}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

@app.post("/api/simula-invaso")
def simula_comportamento(parametri: ParametriSimulazione):
    """
    Il cuore del DSS: prende il volume attuale, applica le piogge (fittizie per 
    l'orizzonte futuro) e sottrae l'apertura manuale richiesta dall'operatore.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Recupera l'ultimo volume reale della diga selezionata
        cursor.execute("""
            SELECT volume_mm3 FROM storico_invasi 
            WHERE UPPER(nome_diga) LIKE UPPER(%s) 
            ORDER BY data_rilevazione DESC LIMIT 1;
        """, (f"%{parametri.nome_diga}%",))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Diga non trovata nello storico.")
            
        vol_iniziale_mm3 = row['volume_mm3']
        
        # 2. Motore Matematico del Bilancio
        date_future = []
        volumi_simulati = [vol_iniziale_mm3]
        piogge_previste = []
        
        # Conversione: da m³/s a Milioni di m³ al giorno (1 m³/s = 0.0864 Mm³/giorno)
        rilascio_giornaliero_mm3 = parametri.apertura_m3s * 0.0864
        
        vol_corrente = vol_iniziale_mm3
        oggi = datetime.now()
        
        for i in range(1, parametri.giorni_previsione + 1):
            giorno_target = oggi + timedelta(days=i)
            date_future.append(giorno_target.strftime("%d/%m/%Y"))
            
            # Per ora simuliamo un pattern meteo, in futuro lo agganceremo a Open-Meteo
            pioggia_mm = random.choice([0.0, 0.0, 2.5, 12.0, 0.0])
            piogge_previste.append(pioggia_mm)
            
            # Afflusso stimato (semplificato) basato sulla pioggia
            afflusso_mm3 = pioggia_mm * 0.25 
            
            # Equazione di bilancio
            vol_corrente = vol_corrente + afflusso_mm3 - rilascio_giornaliero_mm3
            vol_corrente = max(0, round(vol_corrente, 2)) # Impedisce valori negativi
            
            volumi_simulati.append(vol_corrente)
            
        # Aggiustiamo l'array delle date per includere "oggi"
        date_future.insert(0, oggi.strftime("%d/%m/%Y"))
        piogge_previste.insert(0, 0.0)

        return {
            "diga": parametri.nome_diga,
            "rilascio_impostato_m3s": parametri.apertura_m3s,
            "date": date_future,
            "volumi_mm3": volumi_simulati,
            "pioggia_mm": piogge_previste
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("🟢 Avvio Server API Motore Idrologico...")
    uvicorn.run(app, host="127.0.0.1", port=8000)