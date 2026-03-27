# Model Calibration

## Obiettivo

Evitare target fissi e confidence cosmetica. Ogni ticker accumula outcome storici e produce un `ticker_profile` che influenza:

- soglia minima di confidence
- aggressivita dei target
- shrink/expand dei target
- affidabilita del setup

## Pipeline

Per ogni ticker monitorato il job giornaliero:

1. scarica OHLCV daily confermati
2. calcola feature e snapshot
3. genera predizioni storiche bootstrap sulle ultime sessioni
4. confronta le predizioni con gli outcome successivi
5. costruisce `signal_history`
6. aggrega `ticker_profile`
7. genera la predizione piu recente usando il profilo adattivo

## Feature principali

- `atr`
- `adx`
- `rsi`
- trend via `sma50` + stack `ema9/ema21`
- breakout/breakdown
- `volume_ratio`
- `volatility_20d`
- `drawdown_63d`
- `relative_strength_1m`
- `relative_strength_3m`
- distanza da supporto/resistenza in ATR
- regime di mercato (`RISK_ON`, `MIXED`, `RISK_OFF`)

## Outcome valutati

Per ogni predizione vengono misurati:

- `outcome_status`
- `target_1_hit`
- `target_2_hit`
- `stop_hit`
- `max_favorable_excursion`
- `max_adverse_excursion`
- `realized_return_pct`
- `holding_days`
- `target_error`

`target_error` e definito come:

- movimento previsto fino a `target_1`
- meno il massimo movimento favorevole effettivamente osservato

Quindi:

- `target_error > 0`: il sistema ha sovrastimato il target
- `target_error < 0`: il sistema e stato troppo conservativo

## Costruzione del `ticker_profile`

Il profilo aggrega:

- `long_win_rate`
- `short_win_rate`
- `mean_target_error`
- `mean_mae`
- `mean_mfe`
- `avg_days_to_target`
- `avg_days_to_stop`
- `dominant_regime`
- `reliability_score`
- `confidence_floor`
- `target_shrink_factor`
- `target_aggression`

## Come influenza i segnali futuri

### Confidence

`confidence_score` finale = mix di:

- qualita strutturale del setup
- affidabilita storica del ticker

Se il profilo e poco affidabile o con dati insufficienti:

- confidence limitata
- possibile degradazione a `neutral`

### Target

I target nascono da:

- ATR
- struttura tecnica
- supporti/resistenze
- regime

Poi vengono calibrati con:

- `target_shrink_factor`
- `target_aggression`
- errore storico medio del ticker

### Warning flags

Esempi:

- `weak-risk-reward`
- `low-volume`
- `overextended`
- `historical-overestimation`
- `insufficient-data`
- `counter-regime-long`
- `counter-regime-short`

## Limiti attuali

- il profilo usa ancora una calibrazione euristica, non un modello statistico complesso
- la watchlist schedulata e single-user
- la risoluzione stop/target su OHLC daily resta conservativa
- i dati earnings sono opzionali e best-effort

## Evoluzioni consigliate

- engine/version stamping piu esplicito in tutte le tabelle
- priors globali + shrinkage gerarchico per ticker/side/regime
- backtest e live completamente unificati sullo stesso core
- storage outcome piu ricco per tempo di hit e trade state machine
