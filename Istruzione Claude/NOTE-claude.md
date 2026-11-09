# Note per Claude (sessioni future)

Brief completo: `PROGETTO-materasso-interattivo.md` (stessa cartella). Leggerlo solo se serve: sezioni 3-4 e 7 per mat-touch; la parte `pond` (sez. 5) è solo contesto.

## Regole dell'utente
- **Mai fare commit**: li fa sempre l'utente.
- Usare meno token possibile; se qualcosa non è chiaro, chiedere.
- Codice e commenti in inglese, documentazione utente in italiano.

## Stato (2026-11-09)
Base repo creata:
- `mat_touch/config.py`: dataclass `Config` + `load()`/`save()` su `~/.config/mat-touch/config.json` (load tollera file mancante/corrotto e chiavi ignote; save atomico).
- `mat_touch/outputs/base.py`: `OutputBackend.send(touches)`, con `Touches = dict[id, (x, y)]` in pixel CSS; si invia sempre l'insieme completo, dict vuoto = tutte le dita su.
- `mat_touch/outputs/dryrun.py`: stampa i tocchi.
- `mat_touch/__main__.py`: per ora stampa solo la config (TODO M1: wizard).
- Cartelle vuote: `tools/`, `scripts/`, `models/` (ignorata da git tranne `.gitkeep`).
- Prossimo: M1 (camera.py, calibration.py, app.py passo 1).

## Ambiente / problemi aperti
- Python 3.12.3. `tkinter` NON installato: serve `sudo apt install python3-tk`.
- `LICENSE`: MIT (scelta dall'utente, sostituita la Apache 2.0 iniziale).
