# Deploy Free Tier

Stack consigliato:

- `Frontend`: Netlify
- `Database cloud`: Firebase Firestore
- `Scheduler`: GitHub Actions
- `Write API admin`: Netlify Functions
- `Runtime locale`: FastAPI + SQLite

## Perche questa architettura

E la combinazione piu semplice per questo codicebase perche:

- mantiene il core Python senza riscriverlo in JavaScript o Workers
- evita server always-on
- consente un frontend statico gratuito
- permette un job giornaliero automatico
- offre persistenza cloud con sync batch senza obbligare a tenere un backend always-on
- consente scritture online admin senza esporre segreti nel client

## Netlify

- collega il repository a Netlify
- pubblica la root del repo
- usa `index.html` come entrypoint statico
- il frontend legge `static/data/app-state.json`
- le route `/api/*` vengono risolte da Netlify Functions quando il backend locale non c'e

## GitHub Actions

Il refresh giornaliero deve:

1. installare le dipendenze Python
2. eseguire `python -m swing_trading.jobs.daily_refresh`
3. esportare il bundle statico
4. committare il nuovo snapshot se il workflow lo prevede
5. opzionalmente sincronizzare i dati su Firestore

## Firebase

Firestore serve come:

- sync cloud dei dati canonici
- persistenza cloud per watchlist, segnali e posizioni
- base futura per auth e multiutente

Le regole devono restare chiuse di default finche il client non implementa un flusso auth completo.

## Variabili ambiente

Vedi [`.env.example`](.env.example) per:

- `DATABASE_PATH`
- `STATIC_EXPORT_PATH`
- `FIREBASE_PROJECT_ID`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `ADMIN_WRITE_TOKEN`

## Free-tier tradeoff

- `Netlify`: ottimo per static hosting, ma non per compute
- `Firestore`: utile per persistenza, ma con quote da monitorare
- `GitHub Actions`: perfetto per un refresh giornaliero, meno per task frequenti
- `SQLite`: ideale per locale e per il job batch, non per accesso concorrente pesante

## Limiti operativi

- il dato e aggiornato al timestamp dell'ultimo job riuscito
- le scritture hosted sono admin-only e richiedono il token configurato su Netlify
- per un multiutente realtime completo serve ancora auth utente vera davanti alle scritture cloud
