# Signal Engine

## Obiettivo

Generare segnali giornalieri spiegabili, coerenti con il regime di mercato e calibrati per ticker.

## Output del segnale

Per ogni ticker il motore produce:

- `direction`
- `entry_zone`
- `stop_loss`
- `target_1`
- `target_2`
- `optional_target_3` o target probabilistico
- `risk_reward`
- `confidence_score`
- `holding_horizon_estimate`
- `rationale`
- `warning_flags`

## Sorgenti di decisione

Il segnale combina:

- trend e momentum
- ATR e volatilita rolling
- supporti e resistenze
- swing high / swing low
- volume ratio
- regime di mercato
- profilo storico del ticker
- error profile storico del setup

## Logica

### Long

Il motore cerca:

- trend rialzista coerente
- breakout o pullback ordinato
- distanza dallo stop accettabile
- target derivati da ATR e struttura

### Short

Il motore cerca:

- trend ribassista coerente
- breakdown o rimbalzo fallito
- rischio contenuto rispetto allo stop
- target coerenti con supporti e volatilita

### Neutral

Si usa quando:

- il profilo del ticker e debole
- il rischio/reward non e competitivo
- il regime non supporta il setup
- il dato storico e insufficiente

## Explainability

Ogni segnale deve mostrare:

- motivazione sintetica
- fattori principali
- warning flags
- qualita del setup
- relazione con il regime

## Calibrazione

Il segnale non usa target fissi. La calibrazione adatta:

- confidence score
- aggressivita dei target
- shrinkage dei livelli
- reliability label

Se un ticker tende a sovrastimare i target, il profilo deve ridurre l'aggressivita. Se invece il setup e ben comportato, il motore puo mantenere livelli piu ambiziosi.

## Persistenza

Ogni run salva:

- `signals`
- `signal_versions`
- `signal_history`
- `targets`
- `target_revisions`
- `ticker_profiles`

## Limiti

- il motore resta euristico e interpretativo, non predittivo in senso statistico forte
- i segnali dipendono da dati daily confermati
- il comportamento intraday non e coperto
