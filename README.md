# Crypto-Radar – Research-Datenbrücke (November 2026)

GitHub Actions erhebt öffentliche Krypto-Marktdaten, führt **nur Forschungsanalysen und hypothetische Papertrades** aus. Keine Orders, kein Echtgeldhandel, keine automatische Push-Integration von GitHub nach ChatGPT.

## Betrieb

- Workflow: https://github.com/Glumsi0503/crypto-radar/actions/workflows/market-data.yml
- Geplantes GitHub-Intervall: UTC-Minute 7/22/37/52 (best effort, Verzögerung möglich).
- Die fünf separaten ChatGPT-Radare prüfen stündlich und können die öffentlich veröffentlichte Forschungsdatei **nur bei tatsächlicher Abrufbarkeit** auswerten.
- Der Datensammler prüft 50 fest benannte Märkte plus **0 bis 10** dynamisch ausgewählte USDT-Spot-Kandidaten. Diese zusätzlichen Coins werden nur aufgenommen, wenn **Gate.io und eine zweite unabhängige Spotbörse (bevorzugt OKX, alternativ Bitget)** jeweils ausreichenden 24h-USDT-Umsatz und aktuelle, preislich übereinstimmende Ticker melden **und** auf beiden Börsen mindestens 21 zusammenhängende, vollständig geschlossene 15m-Kerzen einschließlich ausreichendem Volumen verifiziert wurden. Die Vorprüfung betrachtet höchstens 150 Gate-Kandidaten und führt maximal 24 aufwendige Zwei-Börsen-Kerzenchecks durch. Bei fehlender Zweitbörse oder Datenqualität bleibt die Zusatzliste leer, ohne die 50 festen Coins auszuschalten. Kein Coin wird dadurch zur Kaufempfehlung.
- 15-Minuten-OHLCV: OKX/Gate/Bitget, unabhängige Bestätigung auf zwei Spotbörsen für Momentum-Research.
- Stunden- und Tagesdaten: 24 ausgewählte Coins auf OKX/Gate. Nicht alle 50 haben diese Zusatzabdeckung.
- Fundamentals: gezielte DefiLlama-Zeitreihen, 7 abgeschlossene UTC-Tage gegen die vorigen 7; echte Token-Wertbindung ist nicht automatisch nachgewiesen.
- Derivate: OKX Funding und Open Interest für wenige ausgewählte Coins; 4h-OI-Änderung erst nach tatsächlich gespeicherten Vergleichssnapshots, kein eigenständiges Squeeze-Signal.
- Echte Smart-Money-Wallet-Käufe sind nicht automatisch vollständig erfasst. Fehlende Daten sind keine positive Bestätigung.
- Bitvavo-DE-Handelbarkeit wird nicht geprüft; Nutzer müssen Börsenverfügbarkeit und Ausführbarkeit selbst kontrollieren.

## Maschinenlesbare Berichte

- `docs/latest.json`: Spot-Kerzendaten, Quellenstatus, Abdeckung
- `docs/discovery.json`: dynamische liquide Forschungs-Ticker
- `docs/enrichment.json`: 1h/1d und begrenzte fundamentale Zeitreihen
- `docs/derivatives.json`: zeitgestempelte Derivate-Snapshots, keine Handelsentscheidung
- `docs/signal_feed.json`: deduplizierte **Research**-Stufen, nicht per Push zugestellt. `recent_events_3h` hilft stündlichen Lesern.
- `docs/radar_inbox.json`: zeitlich und anhand der Fünf-Methoden-Daten geprüfte Forschungs-Kandidaten für die stündlichen ChatGPT-Radare; keine Kaufsignal- oder Push-Freigabe.
- `docs/signal_history.json`, `docs/derivatives_history.json`: Ereignis-/Snapshot-Historie
- `docs/paper_journal.json`, `docs/strategy_status.json`: unverbindliche hypothetische Papertrades, vereinfachte Gebührenannahmen und statistische Auswertung
- `docs/five_method_audit.json`: Fünf-Strategien-Evidenzprüfung mit supported/not_confirmed/not_evaluable je Coin; fehlende Wallet-/Event-Rohdaten verhindern eine Scheinbestätigung
- `docs/observed_outcomes.json` und `docs/observed_outcomes_journal.json`: beobachtete 1/4/24/72h-Signalverläufe; ausgefallene Messfenster werden nicht interpoliert
- `docs/backtest.json`: nächtlicher begrenzter, historischer 15m-Einzelbörsen-Momentum-Test; Annahmen zu Gebühren, Slippage, Next-Open und konservativer Stop-Reihenfolge
- `docs/health.json`: Datenqualitätskontrolle

Bei jedem Lesen müssen `generated_at_utc`, Quellenzeitstempel und `quality` geprüft werden. Ungültige, fehlende oder alte Daten dürfen kein Kaufsignal ergeben. Die GitHub-Datei `signal_feed.json` enthält keine vollständig bestätigten fünf Strategien und keine belegte Push-Zustellung.

## Sicherheit und Tests

```bash
python -m unittest discover -s tests -v
python discovery.py
python market_data.py
python enrichment.py
python derivatives.py
python strategy.py
python signal_feed.py
python healthcheck.py
```

`publish_reports.py` publiziert ausschließlich in GitHub Actions und schützt vor veralteten Berichten und konkurrierenden Pushes. Keine API-Schlüssel oder Kontodaten ins öffentliche Repo schreiben.

**Wichtig:** Der separate [historische Backtest-Workflow](https://github.com/Glumsi0503/crypto-radar/actions/workflows/backtest.yml) läuft nach Zeitplan täglich um 03:13 UTC (Best-Effort) und lässt sich manuell auslösen. Er verifiziert nur eine eng definierte Momentum-Heuristik auf begrenzten historischen Daten, nicht alle fünf Methoden. Ein erfolgreicher GitHub-Workflow bestätigt den Datenfluss, nicht die Wirksamkeit einer Strategie. Ein synthetischer Ende-zu-Ende-Test prüft die Dateiverarbeitung bis zum Radar-Postfach, nicht die tatsächliche Zustellung einer ChatGPT-Mitteilung. Die Papertrade-Checkpoints sind keine nachgewiesenen echten Fills, und die langfristige Profitabilität ist nicht belegt.
