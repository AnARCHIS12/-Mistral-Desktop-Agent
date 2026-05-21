# Mistral Desktop Agent

<p align="center">
  <img src="web/assets/logo.svg" alt="Mistral Desktop Agent logo" width="140" />
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-backend-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img alt="Mistral AI" src="https://img.shields.io/badge/Mistral-AI-FF7000?style=for-the-badge" />
  <img alt="Playwright" src="https://img.shields.io/badge/Playwright-browser-2EAD33?style=for-the-badge&logo=playwright&logoColor=white" />
  <img alt="Telegram" src="https://img.shields.io/badge/Telegram-bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" />
</p>

Agent autonome de controle ordinateur avec FastAPI, WebSocket, Mistral, pyautogui, screenshots OCR, Playwright, SQLite et Telegram.

Site de presentation GitHub Pages: https://anarchis12.github.io/-Mistral-Desktop-Agent/

Pour publier la page: GitHub > `Settings` > `Pages` > source `Deploy from a branch`, dossier `/docs`.

## Installation

## Debutants

Avant de lancer l'application, il faut d'abord recuperer le depot GitHub.

Option simple avec Git:

```bash
git clone https://github.com/AnARCHIS12/-Mistral-Desktop-Agent.git Mistral-Desktop-Agent
cd Mistral-Desktop-Agent
```

Si tu as deja clone sans renommer et que le dossier s'appelle `-Mistral-Desktop-Agent`, entre dedans avec:

```bash
cd -- -Mistral-Desktop-Agent
```

Option sans Git:

1. Ouvre https://github.com/AnARCHIS12/-Mistral-Desktop-Agent
2. Clique `Code`
3. Clique `Download ZIP`
4. Decompresse le fichier ZIP
5. Ouvre le dossier decompresse

Windows:

Double-clique `setup_windows.bat`, puis choisis:

- `1` pour installer
- `2` pour configurer `MISTRAL_API_KEY` et Telegram
- `3` pour lancer

Linux:

```bash
bash launch.sh
```

L'option `1. Installer ou mettre a jour` installe aussi l'OCR par defaut quand c'est possible. Sur Fedora, le script lance:

```bash
sudo dnf install -y tesseract
```

Pour creer un raccourci dans le menu des applications:

```bash
bash create_desktop_launcher.sh
```

Tu peux aussi double-cliquer `Mistral Desktop Agent.desktop` si ton environnement Linux autorise les lanceurs locaux.

Exemple d'objectif:

```text
ouvre Firefox et cherche Bakounine
```


## Expert 

Installation en une commande avec `curl` depuis GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/AnARCHIS12/-Mistral-Desktop-Agent/main/bootstrap.sh | bash
```

Avec configuration non interactive:

```bash
curl -fsSL https://raw.githubusercontent.com/AnARCHIS12/-Mistral-Desktop-Agent/main/bootstrap.sh | \
  MISTRAL_API_KEY=ton_api_key TELEGRAM_BOT_TOKEN=ton_token bash -s -- --yes
```

Choisir le dossier et le port:

```bash
curl -fsSL https://raw.githubusercontent.com/AnARCHIS12/-Mistral-Desktop-Agent/main/bootstrap.sh | \
  bash -s -- --dir "$HOME/.local/share/mistral-agent" -- --port 8001
```

Installation automatique:

```bash
chmod +x install.sh
./install.sh
```

Installation automatique avec lancement direct:

```bash
./install.sh --run
```

Mode non interactif:

```bash
MISTRAL_API_KEY=ton_api_key TELEGRAM_BOT_TOKEN=ton_token ./install.sh --yes
```

Installation manuelle:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

Installe aussi Tesseract OCR sur le systeme:

```bash
sudo apt-get install tesseract-ocr
```

## Configuration

Cree un fichier `.env`:

```env
MISTRAL_API_KEY=ton_api_key
MISTRAL_MODEL=mistral-large-latest
MISTRAL_MIN_SECONDS_BETWEEN_CALLS=20
MISTRAL_RATE_LIMIT_BACKOFF_SECONDS=60
MISTRAL_VISION_MODEL=pixtral-large-latest
ENABLE_VISION_MODEL=true
VISION_EVERY_STEPS=3
TELEGRAM_BOT_TOKEN=ton_token_telegram
ENABLE_TELEGRAM=true
IMPORTANT_CAPTURE_DIR=data/captures
SCREENSHOT_BACKEND=auto
```

`TELEGRAM_BOT_TOKEN` est optionnel. Sans token, le serveur web et l'API fonctionnent normalement.

Si Mistral retourne `429 Too Many Requests`, augmente le delai:

```env
MISTRAL_MIN_SECONDS_BETWEEN_CALLS=30
MISTRAL_RATE_LIMIT_BACKOFF_SECONDS=90
```

La boucle observe deja l'ecran et l'OCR a chaque etape. Le planner Mistral ne recoit donc plus `screenshot` et `ocr` comme outils a appeler, ce qui reduit les appels inutiles.

## Lancement

```bash
python main.py
```

Interface web: http://localhost:48723

## API

- `POST /goal` avec `{ "goal": "..." }`
- `POST /start`
- `POST /pause`
- `POST /resume`
- `POST /stop`
- `GET /status`
- `GET /monitoring`
- `GET /logs`
- `GET /mission`
- `GET /checkpoints`
- `GET /captures`
- `WS /ws`

## Missions longues

L'agent garde maintenant un etat de mission persistant dans SQLite:

- objectif courant
- sous-taches extraites de l'objectif
- etat courant et etape actuelle
- actions reussies/ratees
- erreurs
- captures importantes
- checkpoints apres les actions
- pause/reprise
- detection de stagnation visuelle
- reprise plus lisible apres erreur ou limite API

La page web affiche aussi un panneau `Supervision`:

- temps ecoule
- etape actuelle et prochaine sous-tache
- derniere analyse vision si activee
- captures importantes
- appels Mistral, rate limits et usage API en tokens

Pour ajouter l'analyse image Mistral en plus du screenshot + OCR:

```env
ENABLE_VISION_MODEL=true
MISTRAL_VISION_MODEL=pixtral-large-latest
VISION_EVERY_STEPS=3
```

Passe `ENABLE_VISION_MODEL=false` si tu veux limiter les appels API et eviter des couts supplementaires.

Variables utiles:

```env
MAX_RUNTIME_SECONDS=7200
MAX_STAGNANT_OBSERVATIONS=3
CHECKPOINT_EVERY_STEPS=1
IMPORTANT_CAPTURE_DIR=data/captures
```

## Telegram

Commandes disponibles:

- `/start`
- `/stop`
- `/goal <texte>`
- `/status`

## Securité

Par defaut, l'agent peut acceder a tout l'ordinateur local selon les permissions du compte qui lance l'application:

```env
FILE_ACCESS_MODE=full
ALLOWED_FILE_ROOTS=
TERMINAL_WORKDIR=/home/ton_user
SEARCH_ENGINE=duckduckgo
SCREENSHOT_BACKEND=auto
```

Cela veut dire:

- chemins absolus autorises dans `read_file` et `write_file`
- chemins relatifs resolus depuis `TERMINAL_WORKDIR`
- commandes terminal lancees depuis `TERMINAL_WORKDIR`
- acces reel limite par les permissions du systeme d'exploitation

Si la capture ecran est noire sous Wayland, installe un backend de capture:

```bash
sudo dnf install -y gnome-screenshot grim scrot
```

Le mode `SCREENSHOT_BACKEND=auto` essaie `gnome-screenshot`, `grim`, `spectacle`, `scrot`, puis `mss`.

Pour revenir a un mode limite au dossier du projet:

```env
FILE_ACCESS_MODE=workspace
```

Pour limiter a certains dossiers seulement, garde `FILE_ACCESS_MODE=full` et separe les chemins par `:` sous Linux/macOS:

```env
ALLOWED_FILE_ROOTS=/home/ton_user:/tmp
```

Les commandes terminal destructrices courantes restent bloquees, les erreurs sont limitees a 3 retries, les actions repetees declenchent un arret, et la boucle s'arrete apres `MAX_STEPS`.

## CAPTCHA

Par defaut, les recherches passent par DuckDuckGo pour eviter les CAPTCHA Google:

```env
SEARCH_ENGINE=duckduckgo
```

Autres valeurs possibles:

```env
SEARCH_ENGINE=brave
SEARCH_ENGINE=google
```

Google peut afficher des CAPTCHA avec Playwright. Garde `duckduckgo` si tu veux un agent plus fluide.
