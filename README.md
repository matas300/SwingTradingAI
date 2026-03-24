# Swing Trading AI

Dashboard web per scansione swing trading daily-only con:

- analisi tecnica su chiusure confermate
- contesto di mercato
- news macro e aziendali opzionali
- calendario trimestrali
- autoscan Top 100 USA
- storico persistente in CSV e SQLite

## Avvio locale

```bash
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Apri poi `http://127.0.0.1:8000`.

## File principali

- `swing_trading_ai_improved.py`: motore scanner Python
- `app.py`: backend FastAPI
- `static/`: frontend dashboard
- `start_remote_cloudflare.ps1`: avvio remoto via Cloudflare tunnel
- `stop_remote_cloudflare.ps1`: stop backend e tunnel
