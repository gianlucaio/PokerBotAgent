# PokerBotAgent v0.3.0

Agente autonomo per Texas Hold'em (MTT e Sit'n go) su una piattaforma privata a fiches virtuali, basato su un'architettura **See → Eval → Act** con un modulo aggiuntivo **VOICE** per il controllo/assistenza vocale. Il sistema opera interamente in locale: nessuna API remota, nessun servizio cloud, nessun modello LLM cablato nel codice.

## Indice

- [Architettura](#architettura)
- [Requisiti](#requisiti)
- [Installazione da zero](#installazione-da-zero)
- [Avvio e arresto](#avvio-e-arresto)
- [Avvio tramite GUI](#avvio-tramite-gui-pannello-di-controllo)
- [Test & Verifica (dalla GUI)](#test--verifica-dalla-gui)
- [Modelli consigliati (LM Studio)](#modelli-consigliati-lm-studio)
- [Informazioni torneo](#informazioni-torneo-lettura-automatica-via-vision)
- [Struttura del progetto](#struttura-del-progetto)
- [⚠️ Client e calibrazione](#-client-e-calibrazione)
- [Stato del progetto](#stato-del-progetto)
- [Note](#note)

---

## Architettura

```
    ┌──────────────────────────────────────────────────┐
    │               event-driven loop                  │
    │                                                  │
    │  Vision (2 s) ──→ SEE ──→ EVAL ──→ ACT           │
    │                        ↑                         │
    │                   VoiceModule                    │
    │          (override / correzione / spiegazione)   │
    └──────────────────────────────────────────────────┘
```

- **SEE** cattura lo schermo e legge lo stato del tavolo (carte, pot, stack, timer) via due percorsi complementari: coordinate calibrate (Template Matching + OCR) e un modello Vision locale che legge l'intero screenshot.
- **EVAL** decide l'azione combinando un calcolo matematico deterministico (equity/pot-odds via `Treys`) con un LLM locale (via LM Studio) per il ragionamento contestuale, con fallback a 3 livelli in caso di guasto.
- **ACT** esegue l'azione tramite `PyAutoGUI`, entro un bounding box di sicurezza, con validazione post-click.
- **VoiceModule** è un modulo trasversale opzionale: permette all'utente di dettare una mossa prima del proprio turno, confermare/correggere le decisioni dell'agente in tempo reale, o correggere errori di percezione a voce — senza mai bloccare il loop principale.

---

## Requisiti

| Componente | Minimo | Consigliato |
|---|---|---|
| OS | Linux (X11) | Ubuntu 22.04+ / Debian 12+ |
| Python | 3.10 | 3.11 |
| RAM | 16 GB | 24 GB |
| GPU | Nessuna (funziona su CPU) | VRAM dedicata per LM Studio |
| Tesseract | `tesseract-ocr` | `tesseract-ocr` + lingua italiana |
| LM Studio | Ultima versione | Con modelli caricati |
| Audio | Microfono (per VoiceModule) | Qualsiasi microfono supportato |

---

## Installazione da zero

### 1. Installare le dipendenze di sistema

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv tesseract-ocr portaudio19-dev wmctrl xdotool python3-tk
```

### 2. Installare LM Studio

Scaricare da [lmstudio.ai](https://lmstudio.ai) e installare.

### 3. Scaricare e installare i modelli in LM Studio

Aprire LM Studio e cercare/scaricare i modelli consigliati (vedi sezione dedicata qui sotto).

Assicurarsi che LM Studio sia in esecuzione con i modelli caricati.

### 4. Scaricare il progetto

```bash
# Scarica il file zip da GitHub e estrai nella cartella desiderata
# oppure clona il repository
cd ~/Documenti
unzip PokerBotAgent_v0.3.0.zip
cd "PokerBotAgent v 0.3.0"
```

### 5. Avvio

**Metodo rapido (consigliato):**

```bash
chmod +x avvio.sh
./avvio.sh
```

Lo script crea automaticamente il virtual environment, installa tutte le dipendenze e apre la GUI. Nessun comando aggiuntivo necessario.

**Metodo manuale (da terminale):**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DISPLAY=:0 python3 -u main.py
```

### 6. Posizionare il client

1. Apri il client (app o sito web) nella sua **dimensione di default** (non a schermo intero).
2. Posiziona la finestra nell’angolo in alto a sinistra dello schermo (coordinate 0,0).
3. **Non ingrandire** la finestra.

> **Nota:** ogni utente deve **ricalibrare** le coordinate dei pulsanti e dei seat per il proprio client. Le dimensioni 899×742 si riferiscono al client di sviluppo e non sono valide per altri client.

---

## Avvio e arresto

### Metodo rapido (consigliato per nuovi utenti)

Doppio click su **`avvio.sh`** nella cartella del progetto. Lo script:
1. Verifica che Python3 sia installato
2. Verifica che tutti i file di sistema siano presenti (codice, layout, label carte)
3. Crea automaticamente l'ambiente virtuale (`.venv`) se non esiste
4. Installa tutte le dipendenze da `requirements.txt`
5. **Ripristina automaticamente** eventuali dipendenze mancanti su un venv già esistente
6. Avvia la GUI di configurazione

Nessun comando da terminale necessario — tutto automatico. Anche su un venv già creato, se manca una dipendenza critica (es. OpenCV), `avvio.sh` la reinstalla da `requirements.txt` senza dover ricreare l'ambiente.

**Se qualcosa va storto** (dipendenze mancanti, venv corrotto):
```bash
rm -rf .venv && ./avvio.sh
```

### Avvio manuale (da terminale)

```bash
source .venv/bin/activate
cd <path-progetto>
DISPLAY=:0 python3 -u main.py
```

`DISPLAY=:0` è specifico dell'ambiente X11 e va omesso/adattato su Windows. Il flag `-u` disabilita il buffering dell'output per vedere i log in tempo reale.

**Arresto:** `CTRL+C` nel terminale.

---

## Avvio tramite GUI (pannello di controllo)

La GUI è il pannello di controllo principale. Si apre automaticamente con `avvio.sh`, oppure manualmente:

```bash
source .venv/bin/activate
.venv/bin/python3 gui.py
```

### Sezioni della GUI

- **Torneo:** formato (6-max/9-max/K.O.), blind, durata, stack iniziale, giocatori
- **Moduli:** Vision, Debug Mode, Test Riconoscimento
- **Voice:** abilitazione modulo vocale, sotto-flussi spiegazione e correzione
- **Test & Verifica:** 7 pulsanti per avviare gli script di test (vedi sotto)
- **Nome utente Hero:** campo per inserire il proprio nome utente di gioco (default: "hero")
- **🎨 Tema:** selettore colori con 4 temi (Classica, Scuro, Poker Verde, Blu)
- **Salva & Avvia:** salva la configurazione e lancia il bot
- **Salva configurazione:** salva senza avviare

Il riconoscimento vocale va **azionato esplicitamente dall'utente** (non parte da solo).

---

## Test & Verifica (dalla GUI)

La GUI include una sezione **"🧪 Test & Verifica"** con 7 pulsanti per avviare gli script di test direttamente dalla GUI:

| Test | Scopo |
|---|---|
| **Test Pipeline Completa** | Esegue l'intera pipeline: Vision → Eval → Mouse |
| **Test Vocale** | Verifica microfono + Vosk + parser comandi vocali |
| **Test Visione** | Verifica che il modello Vision legga correttamente le carte |
| **Test 6-max** | Verifica il layout tavolo 6 giocatori |
| **Test 9-max** | Verifica il layout tavolo 9 giocatori |
| **Test Calibrazione** | Ottimizza i parametri della visione |
| **Test Riconoscimento Hero** | Verifica che il bot identifichi correttamente Hero |

Ogni test apre una finestra con output live. Lo script gira in un thread separato (non blocca la GUI). Per avviare un test è necessario che **LM Studio sia in esecuzione** con i modelli caricati.

### Comandi vocali riconosciuti

| Azione | Varianti riconosciute |
|---|---|
| **FOLD** | `fold`, `passo`, `fol`, `foul` |
| **CHECK** | `check`, `controllo`, `ceck` |
| **CALL** | `call`, `chiamo`, `col`, `cal` |
| **ALL-IN** | `all in`, `all-in`, `tutto`, `olin`, `ollin` |
| **RAISE** | `raise`, `rilancia`, `rialza`, `scommetti`, `ri`, `rilamcia` |

Il modello Vosk (piccolo, italiano) a volte interpreta le parole in modo diverso da come pronunciate — le varianti coprono i casi più comuni osservati nei test.

---

## Modelli consigliati (LM Studio)

| Componente | Modello | Uso |
|---|---|---|
| **Visione** | `qwen3-vl-8b-instruct` | Lettura screenshot tavolo (carte, pot, stack, timer, avatar) **+ info torneo dalla barra in alto (blind, ante, giocatori rimasti, paganti)** |
| **Poker** | `texasholdem-llama-3.2-1b-instruct` | Decisione azione (ragionamento contestuale) |

**Note:**
- Il modello Vision deve essere caricato **prima** di avviare il bot (il prompt Vision è gestito in `see.py`, che carica il layout da PokerTableScope).
- Il modello Poker deve essere caricato **prima** di avviare il bot.
- Se il modello Vision non risponde o legge male, verifica che sia effettivamente caricato in LM Studio (la lista `/v1/models` può mostrare modelli non in VRAM).
- Il modello Vision non è deterministico: a volte legge carte corrette, a volte no. Il sistema ha fallback multipli per gestire errori di lettura.

---

## Informazioni torneo (lettura automatica via Vision)

Il bot legge automaticamente le informazioni del torneo **dalla barra informativa in alto al tavolo** (nessuna calibrazione o coordinata necessaria — Vision analizza l'immagine completa):

- **Blind** correnti / prossimo livello (es. `15/30`)
- **Ante** (se presenti, es. `75`)
- **Giocatori rimasti** sul totale (es. `557/577`)
- **Posizioni paganti** in finale / ITM (es. `25`)

Questi dati vengono letti a ogni ciclo Vision e **iniettati nel prompt del modello decisionale**, così il bot adatta la strategia al contesto del torneo (es. più aggressivo con ante, più conservativo vicino al bubble).

I dati inseriti manualmente nella GUI (configurazione torneo) restano disponibili come **fallback** quando Vision non riesce a leggere la barra.

---

## Struttura del progetto

```
PokerBotAgent v 0.3.0/
├── avvio.sh             # Script di avvio (doppio click — crea venv, installa, lancia GUI)
├── main.py              # Entry point, loop di gioco
├── gui.py               # Pannello di controllo grafico (tkinter): configurazione + test + temi colori
├── config.py            # Ambiente/Modalità attivi, soglie, profili tattici, toggle preflop
├── see.py               # Cattura mss + OpenCV + Vision + OCR fallback; carica layout da PokerTableScope
├── eval_engine.py       # Treys + tabelle GTO opzionali + connessione LM Studio + fallback + profilo avversari
├── act.py               # PyAutoGUI + coordinate pulsanti dal layout (PokerTableScope) + validazione + retry click + Sit-Out
├── voice.py             # STT locale Vosk + sotto-flussi comando/spiegazione/correzione
├── db.py                # SQLite: opponent_stats, voice_corrections, tournament_config, perception_corrections
├── tracker.py           # Profilazione avversari (VPIP/PFR/AF ad ogni mano)
├── mem_gc.py            # Garbage Collection: pulizia TTL memoria per sessioni lunghe
├── requirements.txt     # Dipendenze Python (installate automaticamente da avvio.sh)
├── .gitignore           # Esclusioni per distribuzione (venv, cache, screenshot)
├── README.md            # Documentazione completa del progetto
├── memory/              # Memoria persistente per accumulo di motivazioni
├── profiles/            # Profili tattici (tight.json, aggressive.json, ...)
├── layouts/             # Layout caricati da PokerTableScope (esportati dalla GUI del calibratore)
├── assets/deck_labels/  # Label carte per skin (2 colori e 4 colori)
├── models/vosk/         # Modello Vosk italiano — da scaricare (vedi sezione "Il modello Vosk")
├── test/                # Script di test (25+ script: visione, mouse, vocale, pipeline, calibrazione)
└── plugins/             # Skill/moduli futuri, isolati dal core
```

---

## ⚠️ Client e calibrazione

### I layout arrivano da PokerTableScope

Questo progetto (PokerBotAgent) **non calibra** più i tavoli: la calibrazione è demandata a **PokerTableScope**, il calibratore universale che produce i layout JSON che questo bot carica.

**Flusso di calibrazione:**
1. Apri il tavolo nel client (app o sito web) alla dimensione desiderata, posizionalo nell'angolo in alto a sinistra dello schermo
2. Usa **PokerTableScope** per calibrare seat, pulsanti, ROI e dimensioni dei pulsanti
3. Esporta il layout (`layout_<nome>.json`) — PokerTableScope lo copia in `layouts/` con "Esporta e Copia in PokerBotAgent"
4. Questo bot carica il layout selezionato (dropdown in GUI) e usa quelle coordinate per giocare

**Non possiamo divulgare informazioni sulla piattaforma specifica** su cui è stato testato. Ogni utente deve calibrare i propri tavoli con PokerTableScope; le coordinate non valgono da un client all'altro.

### Cosa succede con un client diverso

Non serve modificare il codice: basta calibrare un nuovo layout con PokerTableScope.

1. **Fai uno screenshot del tuo tavolo** (con le azioni visibili per Hero)
2. Apri PokerTableScope e **calibra** seat, pulsanti, ROI, dimensioni pulsanti
3. **Esporta e copia** in `PokerBotAgent/layouts/`
4. Seleziona il nuovo layout nella GUI di PokerBotAgent
5. **Testa la pipeline** con `test_pipeline_completa.py` prima di giocare

### Label carte incluse

Nella cartella `assets/deck_labels/` trovi due set di screenshot delle carte:

- **`label-card-4colori/`** — schema 4 colori (HEARTS=ROSSO, SPADES=NERO, DIAMONDS=BLU, CLUBS=VERDE)
- **`label-card-2colori/`** — schema 2 colori (semi rossi e neri)

Queste label servono per il **Template Matching** (riconoscimento carte via OpenCV). Il modello Vision (qwen3-vl-8b) legge le carte direttamente dallo screenshot e non necessita delle label. Le label sono incluse come riferimento e per la modalità test riconoscimento. Sono quasi standard tra i client di poker, ma potrebbero non corrispondere esattamente alla skin del tuo client.

### Il modello Vosk

Il modello Vosk per il riconoscimento vocale (italiano, ~54MB) **non è incluso nel repository** perché supererebbe il limite di upload di GitHub (25MB per file) e appesantirebbe inutilmente il progetto.

**Installare il modello Vosk:**

```bash
mkdir -p models/vosk

# Opzione A — tramite wget
wget https://alphacephei.com/vosk/models/vosk-model-small-it-0.4.zip -P models/vosk/

# Opzione B — scarica manualmente da https://alphacephei.com/vosk/models/
# Cerca "vosk-model-small-it-0.4" e scarica lo zip, poi mettilo in models/vosk/

# Estrai
cd models/vosk
unzip vosk-model-small-it-0.4.zip
```

Il modello viene caricato automaticamente all'avvio del modulo Voice. Se manca, la GUI mostra un avviso chiaro. Funziona offline, nessuna connessione esterna richiesta.

---

## Stato del progetto

- **Pipeline core (See → Eval → Act) validata end-to-end** su tavolo reale: la Vision legge lo stato dal frame (screenshot o live), il modello poker locale decide l'azione (ricevendo equity/pot-odds da Treys come contesto), l'azione viene mappata sul pulsante corretto (layout da PokerTableScope) e cliccata realmente da PyAutoGUI, con il motore deterministico Treys come rete di sicurezza in caso di fallimento dell'LLM.
- **Layout dall'esterno (PokerTableScope):** il bot carica i layout JSON esportati dal calibratore — nessuna calibrazione hardcoded; il dropdown in GUI seleziona il layout attivo.
- **Modulo VOICE integrato e testato:** riconoscimento vocale offline via Vosk, override vocale pre-turno, varianti italiane per tutti i comandi (fold/fol/foul, check/ceck, call/col/cal, raise/rilamcia/ri, all-in/olin/ollin), persistenza correzioni vocali su DB.
- **GUI con Test & Verifica e temi colori:** pannello di controllo completo con 7 test integrati, 4 temi colori (Classica, Scuro, Poker Verde, Blu).
- **Proposta anticipata:** quando il FLOP appare e non è turno Hero, il modello calcola una proposta che appare a terminale; al turno Hero, l'override vocale vince sulla proposta salvata.
- **Profilazione avversari (Step 12):** il bot traccia le azioni di ogni avversario a ogni mano e aggiorna su DB statistiche VPIP/PFR/AF, iniettandole nel prompt decisionale quando raggiunge almeno 3 mani osservate.
- **Garbage Collection (Step 13):** pulizia automatica della memoria (TTL 600s, limite 200MB) e debug mode scrivono screenshot/log in `/tmp/holdem_debug/` per sessioni lunghe stabili.
- **Info torneo via Vision:** lettura automatica di blind/ante/giocatori/paganti dalla barra in alto a ogni ciclo Vision, iniettati nel prompt decisionale.
- **Distribuzione pronta:** `avvio.sh` con venv automatico (e ripristino dipendenze mancanti), nessun dato personale nel codice, `.gitignore` per esclusioni.
- **Anti-ban offset casuale:** il bot userà le dimensioni (w,h) dei pulsanti dal layout per generare click casuali dentro l'area (in fase di implementazione in `act.py`).
- **Non ancora integrato:** supporto multi-tavolo.

---

## Note

### Limiti noti

- Funziona solo su Linux con X11 (non Wayland)
- Richiede che il tavolo sia posizionato come da layout calibrato (angolo in alto a sinistra dello schermo)
- I modelli LLM devono essere caricati in LM Studio prima dell'avvio
- Il modello Vision non è deterministico: a volte legge carte corrette, a volte no — il sistema ha fallback multipli
- **Ogni client richiede un layout calibrato con PokerTableScope** — le coordinate non valgono da un client all'altro

### Sicurezza

- Nessuna connessione esterna (tranne LM Studio locale)
- Nessun dato personale salvato
- Il database SQLite è locale e non viene condiviso
- Nessuna API key o token nel codice
