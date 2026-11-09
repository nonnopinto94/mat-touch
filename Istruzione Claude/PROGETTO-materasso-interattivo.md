# Materasso interattivo – brief di progetto

> Documento da dare a Claude Code come contesto iniziale. Descrive l'idea, le decisioni già prese e il piano di lavoro. Le decisioni marcate **[DECISO]** non vanno rimesse in discussione senza un motivo concreto; tutto il resto è una proposta modificabile.

## 1. L'idea

Un laghetto con carpe koi viene proiettato dall'alto sul materasso morbido (materassone) di un bambino. Una webcam osserva il materasso. Dove il bambino appoggia una mano (o un piede) il laghetto reagisce: nascono bolle e increspature, i pesci scappano.

Il sistema è diviso in **due progetti indipendenti**:

| Progetto | Cosa fa | Tecnologia |
|---|---|---|
| **pond** (fork di hush-pond) | Il laghetto: grafica, pesci, effetti. Non sa nulla di webcam. Riceve solo normali eventi touch/pointer. | JavaScript vanilla, Canvas 2D, nel browser |
| **mat-touch** | Il "touchscreen virtuale": legge la webcam, trova mani e piedi, li trasforma in tocchi e li invia **solo** alla scheda del browser. | Python 3, OpenCV, MediaPipe, Chrome DevTools Protocol |

Obiettivo di design: **mat-touch deve funzionare con qualsiasi pagina web che accetta il touch**, non solo con il laghetto. Il laghetto è il primo "cliente".

## 2. Hardware

- **PC Linux, sessione X11**, con Chromium (o Google Chrome) installato.
- **Proiettore** montato su un treppiede alto, **di lato al materasso** (non sopra: per ora niente braccio a sbalzo), puntato verso il basso in obliquo. Posizionato su un lato corto del materasso, il più in alto possibile, così l'angolo è ripido e le ombre del bambino sono corte. Keystone del proiettore **spento** se possibile (la deformazione si gestisce nella calibrazione).
- **Webcam USB** da videoconferenza (~20 €), **fissata rigidamente accanto all'obiettivo del proiettore** e rivolta nella stessa direzione. Motivo: se camera e proiettore guardano dallo stesso punto, un oggetto sollevato dal materasso viene visto e illuminato lungo quasi lo stesso raggio, quindi i tocchi cadono dove la luce colpisce la mano (parallasse minima). Deve inquadrare tutto il materasso con un po' di margine.
- Esposizione e bilanciamento del bianco della webcam **bloccati** se la webcam lo permette (`v4l2-ctl --list-ctrls`, poi `v4l2-ctl -c ...`), perché la proiezione che cambia confonde le regolazioni automatiche.
- **Sicurezza fisica**: treppiede fuori dal materasso e zavorrato (soprattutto la gamba opposta al materasso), cavi fissati a terra, proiettore fuori portata. Verificare nel manuale che il proiettore tolleri l'inclinazione verso il basso.
- Prolunga USB: passiva fino a ~5 m, oltre serve una prolunga attiva.

Evoluzioni hardware future (non ora): braccio per proiettare dall'alto in verticale, webcam IR con illuminatore IR, telecamera di profondità.

## 3. Decisione chiave: tocchi solo al browser, via Chrome DevTools Protocol **[DECISO]**

Alternative valutate:

1. **Touchscreen virtuale di sistema (uinput)**: compatibile con ogni applicazione, ma i tocchi raggiungono tutto il PC. Renderlo sicuro con un bambino richiede di chiudere molte vie di fuga (menu contestuali, notifiche, crash del browser che espongono il desktop, gesture del window manager, sessione dedicata). Troppa complessità per il beneficio.
2. **Tocchi iniettati nella scheda del browser via CDP**: Chromium viene avviato con `--remote-debugging-port`, mat-touch si collega e invia `Input.dispatchTouchEvent`. Vantaggi:
   - i tocchi esistono **solo dentro quella scheda**: il desktop non riceve nulla, nemmeno se il browser si chiude;
   - multitouch reale (un id per ogni tocco);
   - per la pagina gli eventi sono identici a quelli di un touchscreen fisico (generano anche Pointer Events con `pointerType: "touch"`), quindi funziona con qualsiasi pagina web senza modificarla;
   - nessun permesso speciale (`/dev/uinput`), nessun `xinput map-to-output`: le coordinate sono direttamente quelle della pagina.

Scelta: **opzione 2**. L'uscita di mat-touch va comunque scritta dietro un'interfaccia astratta (`OutputBackend`) così che in futuro si possa aggiungere un backend uinput senza toccare il resto.

Sicurezza del canale CDP: porta solo su `127.0.0.1` (default di Chromium), profilo Chromium dedicato con `--user-data-dir`, mai il profilo di navigazione personale.

## 4. Progetto `mat-touch` (repository separato)

### 4.1 Flusso dell'interfaccia (wizard)

Finestra desktop semplice, mostrata sullo schermo del PC (non sul proiettore). Tecnologia: **Tkinter** (libreria standard) + **Pillow** per mostrare i fotogrammi. Niente framework pesanti.

**Passo 1 – Camera e contorni della proiezione**
- Scelta della webcam (elenco dei `/dev/video*` disponibili) e anteprima dal vivo.
- L'utente clicca i **4 angoli dell'area proiettata** nell'immagine della webcam. I punti restano trascinabili per correggerli. L'ordine dei click non conta: il programma li ordina da solo (alto-sinistra, alto-destra, basso-destra, basso-sinistra).
- Il poligono viene disegnato sopra l'anteprima. Pulsanti: "Ricomincia", "Conferma".
- Dai 4 punti si calcola l'omografia camera → area proiettata normalizzata `[0,1]×[0,1]` con `cv2.getPerspectiveTransform`.

**Passo 2 – Collegamento al browser**
- Campo per la porta CDP, precompilato con `9222`. Pulsante "Collega".
- mat-touch interroga `http://127.0.0.1:<porta>/json`, elenca le schede di tipo `page` e, se ce n'è una sola, la seleziona da sé; altrimenti l'utente sceglie dall'elenco.
- Se la connessione fallisce, messaggio chiaro con il comando corretto per lanciare Chromium.
- Ottiene le dimensioni del viewport (`Page.getLayoutMetrics` o `Runtime.evaluate` di `innerWidth/innerHeight`) e le aggiorna se cambiano.

**Passo 3 – In funzione**
- Anteprima con sovrapposti: poligono calibrato, scheletro/punti rilevati, tocchi attivi con il loro id.
- Pulsante grande **Pausa/Riprendi tocchi**.
- Pochi cursori: soglia di confidenza, fotogrammi per "entrare"/"uscire", forza del filtro di smoothing.
- Modalità **test senza visione**: cliccando sull'anteprima si invia un tocco al punto corrispondente della pagina. Serve a verificare calibrazione e collegamento senza bambino e senza MediaPipe.

Configurazione salvata in `~/.config/mat-touch/config.json` (camera, 4 angoli, porta, parametri). All'avvio, se esiste una configurazione valida, si propone "Usa la calibrazione salvata".

### 4.2 Pipeline per ogni fotogramma

1. **Acquisizione** – OpenCV `VideoCapture` (backend V4L2), risoluzione moderata (es. 1280×720 o 960×540), fps il più alto stabile.
2. **Rilevamento** – MediaPipe Tasks (pacchetto Python `mediapipe`, API *Tasks*, non le vecchie *solutions*). Backend selezionabile:
   - **Pose (predefinito)**: `PoseLandmarker`, `num_poses` 2–3 (fratelli, genitori). Punti usati:
     - mano sinistra/destra = media di polso (15/16), indice (19/20), mignolo (17/18);
     - piede sinistro/destro = punta del piede (31/32), opzionale.
     - Motivo: in obliquo la camera vede il bambino quasi frontalmente, e la posa del corpo è più robusta delle mani viste piccole.
   - **Hands**: `HandLandmarker`, `num_hands` 4, punto = centro del palmo o punta dell'indice. Utile se la camera è vicina.
   - Filtrare per `visibility`/`presence` sotto soglia.
   - Modello scaricato automaticamente in `models/` al primo avvio (non committato).
3. **Mappatura** – punto camera → omografia → coordinate normalizzate → pixel CSS del viewport. Scartare i punti fuori dal poligono (con un piccolo margine configurabile).
4. **Tracking** – MediaPipe non garantisce identità stabili tra fotogrammi. Associazione con il vicino più prossimo (o algoritmo ungherese) tra i punti nuovi e i tocchi attivi, con distanza massima. Ogni tocco ha un id stabile finché esiste.
5. **Anti-rimbalzo** – un tocco "nasce" solo dopo N fotogrammi consecutivi (es. 2–3) e "muore" dopo M fotogrammi di assenza (es. 4–6).
6. **Smoothing** – filtro **One Euro** per ogni tocco (poco ritardo nei movimenti rapidi, niente tremolio da fermo).
7. **Uscita** – invio dello stato al backend.

Semantica del tocco (con una sola webcam non si distingue "appoggiato" da "sospeso", ed è accettabile per un gioco): punto che compare nell'area = dito giù; si muove = trascinamento; sparisce o esce = dito su.

### 4.3 Backend CDP

- Client WebSocket sincrono (`websocket-client`) in un thread dedicato, con riconnessione automatica se il browser si riavvia.
- All'avvio della connessione:
  - `Emulation.setTouchEmulationEnabled` con `enabled: true`, `maxTouchPoints: 10`, così la pagina si comporta come su un dispositivo touch;
  - `Page.addScriptToEvaluateOnNewDocument` + `Runtime.evaluate` di un piccolo script di "indurimento" generico, valido per qualsiasi pagina: blocca `contextmenu` (la pressione lunga non apre menu), disattiva la selezione del testo, imposta `touch-action: none` sul documento.
- Invio tocchi con `Input.dispatchTouchEvent`. A ogni aggiornamento si invia l'**insieme completo** dei tocchi attivi (`touchStart` se compare un id nuovo, altrimenti `touchMove`); Chromium calcola da sé quali punti sono stati premuti, mossi o sollevati. Quando non resta nessun tocco si invia `touchEnd` con lista vuota. **Da verificare sulla documentazione CDP e con la pagina di test** (vedi 4.5) il comportamento esatto quando si solleva un solo dito su più.
- Limitare la frequenza di invio (es. massimo 60 eventi/s) e non inviare nulla se nulla è cambiato.
- Comandi da tastiera mentre la scheda kiosk ha il focus: con `Runtime.addBinding` la pagina può chiamare una funzione esposta da mat-touch. Lo script iniettato ascolta, per esempio, `Ctrl+Alt+P` (pausa tocchi) e `Ctrl+Alt+Q` (chiudi tutto) e li inoltra a mat-touch.

### 4.4 Struttura proposta

```
mat-touch/
  mat_touch/
    __main__.py          # avvio: python -m mat_touch
    app.py               # wizard Tkinter (passi 1-3)
    camera.py            # elenco e apertura webcam
    calibration.py       # ordinamento angoli, omografia, salvataggio
    detectors/
      base.py
      pose.py            # PoseLandmarker
      hands.py           # HandLandmarker
    tracker.py           # associazione, id, anti-rimbalzo
    filters.py           # One Euro
    outputs/
      base.py            # OutputBackend (interfaccia)
      cdp.py             # Chrome DevTools Protocol
      dryrun.py          # stampa i tocchi, per test
    config.py
  tools/
    touch-test.html      # pagina che disegna i tocchi ricevuti (id, posizione, tipo evento)
  scripts/
    start.sh             # avvia tutto (vedi sezione 6)
  models/                # scaricati al primo avvio, in .gitignore
  requirements.txt       # opencv-python, mediapipe, numpy, pillow, websocket-client
  README.md
  LICENSE                # MIT
```

Dipendenza di sistema: `python3-tk`. Ambiente virtuale `venv`, **niente Docker** (servirebbero passaggi espliciti di webcam e display senza alcun vantaggio).

### 4.5 Test senza proiettore

Tutto deve essere sviluppabile sul portatile: Chromium in una finestra normale su `tools/touch-test.html`, webcam del portatile, si "calibra" cliccando gli angoli di un foglio o dello schermo, e si verifica che i tocchi compaiano nella pagina di test. La modalità "click sull'anteprima" del passo 3 permette di provare il backend CDP anche senza rilevamento.

## 5. Progetto `pond` (fork di hush-pond)

- Origine: https://github.com/jeiel85/hush-pond, licenza **MIT**, copyright jeiel85. Il file `LICENSE` originale va mantenuto. Nel README va scritto chiaramente che la simulazione del laghetto è sua e il fork aggiunge le modifiche per la proiezione interattiva.
- JavaScript vanilla, Canvas 2D, nessuna build. Si serve in locale con `python -m http.server 8417`. Parametro utile già esistente: `?ui=0` nasconde l'interfaccia.

### 5.1 Stato attuale dell'input (da `js/main.js`)

- `pointerdown` sul canvas: dà da mangiare (`world.feed`) e inizia un trascinamento; **ignora i puntatori non primari** (`if (!e.isPrimary) return;`), quindi oggi gestisce un dito solo.
- `pointermove`: se il movimento è molto veloce chiama `world.scare` (i pesci scappano); durante il trascinamento chiama `world.stir` (increspature).
- `lastMove` è una variabile **unica e condivisa**: con più puntatori, il "salto" tra due dita diverse verrebbe letto come un movimento rapidissimo e scatenerebbe spaventi falsi.
- Il CSS ha già `touch-action: none`.

### 5.2 Modifiche richieste

1. **Multitouch vero**: stato separato per ogni `pointerId` (posizione precedente, tempo, distanza percorsa) in una `Map`, pulito su `pointerup`/`pointercancel`. Rimuovere il filtro `isPrimary`.
2. **I pesci scappano da ogni tocco attivo**, non solo dai movimenti rapidi: a ogni frame, per ogni tocco presente, una spinta di fuga sui pesci entro un raggio (riusare `world.scare` o aggiungere un metodo dedicato più "continuo").
3. **Bolle**: nuovo effetto nel modulo degli effetti (`js/effects.js`): quando un tocco compare nascono alcune bolle, e mentre resta fermo continuano a nascerne poche. Le bolle viste dall'alto: cerchi chiari che si allargano leggermente, salgono di luminosità e scoppiano con un'increspatura.
4. **Cibo**: il tocco oggi dà sempre da mangiare. Renderlo configurabile (es. `?feed=0|1`) perché con un bambino che tocca di continuo i pesci verrebbero attirati invece di scappare. Predefinito per la modalità proiezione: niente cibo al tocco, oppure solo con un tocco molto breve.
5. **Preset proiezione**: un parametro (es. `?mode=mat`) che attiva `ui=0`, i comportamenti sopra e colori leggermente più contrastati, perché su un materasso la proiezione perde saturazione.

Il fork **non deve sapere nulla di webcam o CDP**: riceve solo eventi pointer/touch. Così lo si prova anche su un tablet o con il mouse.

## 6. Avvio di tutto (`start.sh`)

1. Avvia il server del laghetto: `python -m http.server 8417` nella cartella di `pond`.
2. Avvia Chromium in kiosk sull'uscita del proiettore, per esempio:
   ```
   chromium --kiosk --user-data-dir="$HOME/.config/mat-touch/chromium" \
     --remote-debugging-port=9222 --no-first-run --noerrdialogs \
     --disable-pinch --overscroll-history-navigation=0 \
     "http://127.0.0.1:8417/?mode=mat"
   ```
   (Con due schermi, la finestra va posizionata sull'uscita del proiettore, es. `--window-position=<x>,0`.)
3. Avvia `python -m mat_touch`, che propone la calibrazione salvata e si collega alla porta 9222.
4. Alla chiusura di mat-touch, termina anche Chromium e il server.

## 7. Piano di lavoro (milestone)

1. **M1 – Camera e calibrazione**: wizard passo 1, ordinamento angoli, omografia, salvataggio config.
2. **M2 – Collegamento CDP**: passo 2, elenco schede, viewport, `tools/touch-test.html`, modalità "click sull'anteprima = tocco". A fine M2 la catena calibrazione → browser è verificata senza visione artificiale.
3. **M3 – Rilevamento**: backend Pose (poi Hands), disegno dei punti nell'anteprima.
4. **M4 – Tracking e tocchi**: id stabili, anti-rimbalzo, One Euro, invio multitouch via CDP, script di indurimento, comandi da tastiera.
5. **M5 – Fork del laghetto**: modifiche della sezione 5.2.
6. **M6 – Avvio e rifinitura**: `start.sh`, riconnessione, parametri v4l2 della webcam, README per entrambi i progetti.

## 8. Principi

- Semplicità prima di tutto: poche dipendenze, niente servizi superflui, niente Docker.
- I due progetti restano disaccoppiati: l'unico contratto tra loro sono gli eventi touch standard del browser.
- Ogni pezzo deve essere provabile da solo (mouse sul laghetto, pagina di test per mat-touch, modalità click per il backend).
- Codice e commenti in inglese, documentazione utente in italiano.
