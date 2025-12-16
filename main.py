import requests
import os
import sys

# --- I TUOI DATI VERIFICATI ---
TELEGRAM_TOKEN = "8537876026:AAGuT5iNObiUlU0OkN-VQ3PXQRWVDWRBjus"
TELEGRAM_CHAT_ID = "-1003527149783"

def main():
    print("--- AVVIO TEST DI CONNESSIONE ---")
    
    # URL per inviare un semplice messaggio di testo
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # Il messaggio che vedrai sul canale
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "✅ CONNESSIONE RIUSCITA!\nSe leggi questo messaggio, il Bot è perfettamente operativo e collegato a GitHub."
    }
    
    try:
        print(f"Tentativo invio a: {TELEGRAM_CHAT_ID}...")
        response = requests.post(url, data=payload)
        
        # Stampiamo il risultato tecnico
        print(f"Status Code: {response.status_code}")
        print(f"Risposta Telegram: {response.text}")
        
        if response.status_code == 200:
            print(">>> SUCCESSO! Controlla il canale Telegram.")
        else:
            print(">>> ERRORE. Leggi la risposta Telegram qui sopra.")
            
    except Exception as e:
        print(f"Errore critico nello script: {e}")

if __name__ == "__main__":
    main()
