# Position Lifecycle

## Modello

La posizione reale non va trattata come un record statico. La fonte di verita e la sequenza di eventi.

Eventi supportati:

- `OPEN`
- `ADD`
- `REDUCE`
- `CLOSE`
- `UPDATE_STOP`
- `UPDATE_TARGETS`
- `MANUAL_NOTE`
- `SYSTEM_RECOMMENDATION`

## Entita principali

- `open_positions`: sintesi corrente della posizione
- `position_events`: audit trail completo
- `position_daily_snapshots`: fotografia giornaliera
- `position_recommendations`: raccomandazione operativa

## Regole di calcolo

### `OPEN`

- crea la posizione reale
- salva entry iniziale, side, quantita e timestamp
- inizializza target originari e target adattivi

### `ADD`

- aumenta la quantita
- ricalcola il prezzo medio di carico
- mantiene memoria dell'entry iniziale

### `REDUCE`

- chiude solo una parte della posizione
- aggiorna quantity residua
- aggiorna realized PnL

### `CLOSE`

- chiude il residuo
- la posizione resta `open` finche la quantity residua e maggiore di zero

## Formule operative

- `initial_entry_price`: primo prezzo effettivo di apertura
- `average_entry_price`: costo medio reale dopo tutti gli eventi
- `current_quantity`: quantita residua
- `initial_quantity`: quantita iniziale aperta
- `realized_pnl`: PnL gia cristallizzato da `REDUCE` e `CLOSE`
- `unrealized_pnl`: PnL aperto sulla quantita residua
- `total_pnl = realized_pnl + unrealized_pnl`
- `gross_exposure`: esposizione corrente in valore assoluto
- `holding_days`: giorni tra apertura e data di valutazione
- `max_favorable_excursion`: massimo movimento favorevole rispetto all'entry iniziale
- `max_adverse_excursion`: massimo movimento avverso rispetto all'entry iniziale

## Target

La UI deve mostrare sempre due prospettive:

- `targets_from_original_signal`
- `current_adaptive_targets`

La seconda prospettiva si aggiorna nel tempo, ma non deve perdere il riferimento all'entry iniziale.

## Raccomandazione giornaliera

La recommendation engine separata dal signal engine restituisce:

- action: `add`, `maintain`, `reduce`, `close`, `no_action`
- confidence
- rationale leggibile
- suggested stop update
- suggested target update
- suggested size action
- warning flags

La logica deve dipendere da:

- stato del segnale originario
- regime del ticker
- distanza da stop e target
- performance storica del setup
- qualita del ticker profile
- stato economico della posizione reale

## Esempi

### Maintain

Trend ancora coerente, momentum in rallentamento ma non rotto, target vicino ma rischio sotto controllo.

### Reduce

Il segnale resta vivo ma la probabilita di estensione si e ridotta, oppure la volatilita e aumentata.

### Add

Pullback ordinato dentro un trend ancora valido, con rischio totale ancora entro il budget.

### Close

Prezzo troppo vicino allo stop, flip del segnale, oppure setup indebolito in modo sostanziale.

## Auditabilita

Ogni azione deve lasciare traccia:

- evento registrato
- snapshot giornaliero
- recommendation storicizzata
- target revision storicizzata

## Limiti

- il calcolo resta daily e non intraday
- `realized_pnl` e `unrealized_pnl` dipendono dal prezzo mark disponibile al refresh
- le fee possono essere opzionali e zero se non fornite
