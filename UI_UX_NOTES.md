# UI UX Notes

## Direzione

La UI deve sembrare una vera app operativa, non una homepage monolitica. La scelta visiva e sobria, leggibile e professionale.

## Informazione

Viste richieste:

- `Overview`
- `Study Watchlist`
- `Signals`
- `Open Positions`
- `Position Detail`
- `Ticker Detail`
- `History`
- `Settings`

## Distinzione chiave

- `Study Watchlist`: ticker osservati, nessun capitale impegnato
- `Open Positions`: trade reali dell'utente, con eventi e recommendation history

## Flussi UX

### 1. Ticker in studio

L'utente aggiunge ticker alla watchlist, il job li analizza ogni giorno e la UI mostra segnali, target e confidence.

### 2. Apertura posizione reale

Dalla vista segnale o ticker detail l'utente apre una posizione reale con quantita, prezzo, ora e note.

### 3. Incremento o riduzione

Dalla posizione aperta l'utente puo registrare `ADD` e `REDUCE`, aggiornando media di carico e PnL.

### 4. Review giornaliera

La vista `Open Positions` mostra ogni giorno la raccomandazione operativa e lo stato economico della posizione.

## Componenti UI

- sidebar o tab navigation
- KPI cards
- tabelle filtrabili
- pannelli dettaglio
- timeline eventi
- confronto tra target originari e adattivi
- badge di raccomandazione
- grafici sobri
- empty/loading/error states curati
- dark mode ben leggibile
- mobile support

## Design system

- palette grafite / sabbia per light mode
- slate / ink per dark mode
- font gratuiti e leggibili
- gerarchia forte
- microcopy breve
- niente look crypto rumoroso

## Stati

- loading: skeleton o empty state dedicato
- error: messaggio breve e utile
- static mode: indicazione chiara che i dati arrivano da snapshot
- live/local mode: refresh manuale disponibile

## Note pratiche

- l'UX deve favorire lettura rapida e confronto tra watchlist e posizioni
- i dettagli di posizione devono mettere in evidenza eventi, target e ultima recommendation
- i warning flags devono essere visibili ma non invadenti
