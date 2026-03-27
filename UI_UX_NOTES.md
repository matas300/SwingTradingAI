# UI UX Notes

## Direzione

Obiettivo: superficie di ricerca sobria, leggibile, premium, non crypto-dashboard.

Scelte implementate:

- sidebar con viste separate
- header compatto al posto di hero monolitica
- cards KPI pulite
- tabella segnali vera
- dettaglio ticker separato
- palette graphite/sand in light mode e slate/ink in dark mode
- font `Manrope` + `IBM Plex Sans` + `IBM Plex Mono`

## Architettura informativa

- `Overview`
  KPI, actionable setups, ultime outcome
- `Watchlist`
  universo tracciato, filtri, pin locali
- `Ticker Detail`
  sparkline, target, profilo adattivo, top factors, signal history
- `Signals`
  tabella completa dei piani attivi
- `History`
  tape degli outcome
- `Settings`
  preferenze UI e gestione watchlist locale/API

## Principi

- `Actionable first`
  i setup interessanti salgono, i neutral non dominano la schermata
- `Explainability visible`
  top factors, warning flags e rationale sono mostrati nel dettaglio ticker
- `Read-heavy optimized`
  la UI parte da snapshot statico; niente scansioni automatiche al bootstrap
- `Mobile-first enough`
  layout a stack semplice, senza forzare tabelle compresse illeggibili

## Stati

- loading: empty state dedicato
- error: pannello chiaro con messaggio
- empty: messaggi specifici per signals/history/watchlist
- static mode: badge e copy espliciti
- api mode: refresh disponibile

## Limiti attuali

- non c'e ancora un chart engine avanzato, ma uno sparkline SVG sobrio
- le preferenze multiutente reali non sono attive nel deploy statico
- la watchlist modificabile dal frontend resta una feature locale/API, non del deploy Netlify read-only
