name: Aggiornamento Dati ARPAB

on:
  schedule:
    - cron: '0 * * * *'  # Esegue ogni ora
  workflow_dispatch:      # Permette avvio manuale

jobs:
  scrape:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Installazione Playwright
        run: |
          pip install playwright
          playwright install chromium --with-deps

      - name: Esecuzione Scraper
        run: python scraper_arpab.py

      - name: Commit e Push dei risultati
        run: |
          git config --global user.name 'github-actions[bot]'
          git config --global user.email 'github-actions[bot]@users.noreply.github.com'
          # Crea la cartella data se non esiste per prevenire errori git
          mkdir -p data
          git add data/
          git commit -m "Auto-update ARPAB sensors: $(date)" || echo "Nessun cambiamento da caricare"
          git push
