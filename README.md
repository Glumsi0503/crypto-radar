# Crypto-Radar – Research-Datenbrücke (November 2026)

GitHub Actions erhebt öffentliche Krypto-Marktdaten, führt **nur Forschungsanalysen und hypothetische Papertrades** aus. Keine Orders, kein Echtgeldhandel, keine automatische Push-Integration von GitHub nach ChatGPT.

## Betrieb

- Workflow: https://github.com/Glumsi0503/crypto-radar/actions/workflows/market-data.yml
- Geplantes GitHub-Intervall: UTC-Minute 7/22/37/52 (best effort, Verzögerung möglich).
- Die fünf separaten ChatGPT-Radare prüfen stündlich und können die öffentlich veröffentlichte Forschungsdatei **nur bei tatsächlicher Abrufbarkeit** auswerten.
- Der Datensammler prüft 50 fest benannte Märkte plus bis zu zehn frisch entdeckte liquide USDT-Spot-Kandidaten. Neue Börsenticker sind keine Empfehlungen und müssen OHLCV-Gültigkeitsprüfungen bestehen.
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
- `docs/signal_history.json`, `docs/derivatives_history.json`: Ereignis-/Snapshot-Historie
- `docs/paper_journal.json`, `docs/strategy_status.json`: unverbindliche hypothetische Papertrades, vereinfachte Gebührenannahmen und statistische Auswertung
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

**Wichtig:** Ein erfolgreicher GitHub-Workflow bestätigt den Datenfluss, nicht die Wirksamkeit einer Strategie. Die Papertrade-Checkpoints sind keine nachgewiesenen echten Fills, und die langfristige Profitabilität ist nicht belegt.
