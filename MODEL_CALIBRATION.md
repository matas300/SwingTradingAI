# Model Calibration

## Obiettivo

Evitare target cosmetici e confidence fissa. Ogni ticker costruisce un profilo adattivo che influenza segnali, target e raccomandazioni sulle posizioni.

## Pipeline

Per ogni ticker il refresh giornaliero:

1. scarica OHLCV daily confermati
2. costruisce le feature tecniche
3. genera segnali e target
4. confronta i segnali storici con gli outcome osservati
5. aggiorna `ticker_profiles`
6. ricalibra confidence e target

## Metriche profilo

Il `ticker_profile` include almeno:

- volatilita rolling
- ATR rolling
- trend persistence
- gap behavior
- long win rate
- short win rate
- setup-specific win rate
- average time to target
- average time to stop
- target overshoot rate
- target undershoot rate
- MFE medio
- MAE medio
- confidence calibration error
- regime distribution

## Calibrazione target

I target nascono da:

- ATR
- supporti / resistenze
- swing highs / lows
- volatilita storica
- regime di mercato

Poi vengono corretti con:

- baseline target
- error profile del ticker
- de-rating se il modello sovrastima
- aggressivita maggiore solo quando statisticamente giustificata
- versioning temporale dei target

## Calibrazione confidence

La confidence finale non dipende solo dal setup corrente. Viene ridotta quando:

- il ticker ha pochi dati
- il profilo e instabile
- il regime e sfavorevole
- il setup storico e poco affidabile

Viene alzata quando:

- il setup e coerente
- il profilo storico e robusto
- il comportamento del ticker e stabile

## Regole pratiche

- se il profilo mostra sovrastima sistematica dei target, ridurre l'aggressivita
- se il profilo e debole, degradare la fiducia operativa
- se il regime e contrario al setup, mantenere piu conservativo il profilo target

## Limiti

- la calibrazione e euristica e interpretabile
- non e un modello statistico gerarchico completo
- i valori giornalieri rimangono sensibili alla qualita del dato di mercato
