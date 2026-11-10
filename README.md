# Crypto-Radar – öffentliche Marktdatenbrücke

Status (10. November 2026): Collector, Tests und GitHub-Actions-Workflow sind installiert. **Der erste erfolgreiche Live-Datenlauf und die Anbindung an ChatGPT-Automationen sind noch nicht nachgewiesen.**

## Test und laufende Datenerhebung

- [GitHub Actions – Crypto radar public market data](https://github.com/Glumsi0503/crypto-radar/actions/workflows/market-data.yml)
- Der Workflow ist auf UTC-Minuten 7/22/37/52 je Stunde angesetzt. GitHub-Schedules sind Best-Effort und können verzögert werden.
- Nach einem erfolgreichen Lauf wird der Bericht unter `docs/latest.json` abgelegt. Öffentliche Rohansicht: https://raw.githubusercontent.com/Glumsi0503/crypto-radar/main/docs/latest.json
- Unter `quality.valid_checks` muss **>0** stehen, bevor von nutzbaren Live-Marktdaten gesprochen werden darf. Das Feld `quality.full_market_coverage` bleibt `false`.
- `research_only` bezeichnet rein technische Beobachtungen. Es gibt **keine Handelsalarme** und keine Bitvavo-DE-Verifikation.

## Abdeckung

Pilotliste: BTC, ETH, SOL, LINK, AAVE, UNI, AVAX, NEAR, ATOM, INJ, ARB und OP auf USDT-Spotmärkten der Börsen Binance, Bybit und OKX. Vergleich auf Basis von 21 vollständig geschlossenen und zusammenhängenden 15-Minuten-Kerzen. Preisplus mindestens 3 % in einer Kerze und Quote-Volumen mindestens 3× Durchschnitt der vorangehenden 20 vollständig geschlossenen Kerzen, bei zwei unabhängigen Börsen zum gleichen Kerzenzeitpunkt.

**Grenzen:** Nicht der gesamte Kryptomarkt. Keine 1h-Alternative, keine OI-/Funding-Daten, keine Wallet-/Fundamentaldaten, keine sichere regionale Bitvavo-DE-Spotfreigabe und kein implementierter Zugriff aus den fünf ChatGPT-Wächtern. Kein automatischer oder manueller Echtgeldhandel.

## Sicherheit

Nur öffentliche API-Endpunkte. Keine API-Schlüssel, keine Wallet-Verknüpfung, keine Orders. Keine privaten Informationen oder Credentials ins öffentliche Repository schreiben.

## Lokaler Test

```bash
python -m unittest discover -s tests -v
python market_data.py
```

Falls GitHub Actions keine Dateien schreiben darf: Repository Settings > Actions > General > Workflow permissions > **Read and write permissions** aktivieren. Fehlende Schreibberechtigung verhindert die Aktualisierung der JSON-Datei; sie sollte nicht als erfolgreicher Datenlauf gewertet werden.


## Forschungsstrategie und Papertrade-Journal

Seit 10. November 2026 ergänzt `strategy.py` die 15-Minuten-Datenerhebung um ein vorsichtiges, **nicht für Echtgeld freigegebenes** Konsens-Momentum-Modell:

- Mindestens zwei verschiedene öffentliche SPOT-Börsen bestätigen dasselbe abgeschlossene 15-Minuten-Fenster.
- Kerzenplus 2–8 %, auf beiden Börsen Quote-Volumen mindestens 2× über dem Durchschnitt der vorherigen 20 abgeschlossenen Kerzen.
- Mindestens 100.000 USDT gehandeltes Quote-Volumen je Börse und höchstens 1 % Kursabweichung zwischen den Referenzbörsen.
- Maximal drei offene Papierpositionen; Modell-Loss-Checkpoint −2,5 %, Ziel-Checkpoint +5 %, maximale Haltedauer 72 Stunden. Annahme: 0,25 % Gebühren pro Seite, Slippage nicht modelliert.
- Open/Closed-Status und hypothetische Nettoergebnisse in `docs/paper_journal.json`; Zusammenfassung in `docs/strategy_status.json`, **erst nach erfolgreichem Workflow-Lauf**.
- Trigger beruhen auf abgefragten Momentankursen: Ein Kurs, der zwischen zwei Läufen das Ziel oder Stop-Level berührt, wird möglicherweise verpasst. Das ist **keine realistische Ausführungssimulation**; keine Aussage zur tatsächlichen Profitabilität.
- Alle fünf ChatGPT-Wächter enthalten Prüfhinweise zur Datenbrücke. Dass ihre Laufumgebung GitHub-Daten tatsächlich lesen kann, ist separat zu verifizieren.

Ein gewünschtes Gewinnverhältnis von sieben profitablen Signalen aus zehn ist keine vorab garantierbare oder aus wenigen simulierten Positionen belegbare Erfolgsquote. Erwartungswert, Risikokontrolle und realistische Gebühren-/Slippageannahmen sind wichtiger als eine hohe bloße Trefferquote.

Keine Kundenkonto-API-Schlüssel, keine private Token-/Kaufbarkeitsverifizierung, keine Orders, kein Echtgeld-Auto-Trading.
