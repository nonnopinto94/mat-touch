# mat-touch

"Touchscreen virtuale" per superfici proiettate: una webcam osserva l'area proiettata, trova mani e piedi (MediaPipe) e li invia come tocchi multitouch **solo** a una scheda di Chromium, tramite Chrome DevTools Protocol. Funziona con qualsiasi pagina web che accetta il touch.

## Installazione

```
sudo apt install python3-tk python3-venv
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Avvio

Chromium con la porta di debug (profilo dedicato, mai quello personale):

```
chromium --user-data-dir="$HOME/.config/mat-touch/chromium" --remote-debugging-port=9222 <url>
```

Poi:

```
python -m mat_touch
```

La configurazione è salvata in `~/.config/mat-touch/config.json`.

Stato: in sviluppo.
