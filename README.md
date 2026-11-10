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
