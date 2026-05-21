#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

APP_NAME="Mistral Desktop Agent"

green="$(printf '\033[32m')"
yellow="$(printf '\033[33m')"
red="$(printf '\033[31m')"
reset="$(printf '\033[0m')"

log() {
  printf '%s\n' "${green}==>${reset} $*"
}

warn() {
  printf '%s\n' "${yellow}Warning:${reset} $*"
}

fail() {
  printf '%s\n' "${red}Error:${reset} $*" >&2
  read -r -p "Appuie sur Entree pour fermer..." _
  exit 1
}

pause() {
  read -r -p "Appuie sur Entree pour continuer..." _
}

normalize_bool() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    y|yes|oui|o|true|1|on) printf '%s' "true" ;;
    n|no|non|false|0|off) printf '%s' "false" ;;
    *) printf '%s' "$1" ;;
  esac
}

configure_env() {
  printf '\nConfiguration .env\n'
  read -r -p "MISTRAL_API_KEY: " mistral_key
  read -r -p "TELEGRAM_BOT_TOKEN optionnel: " telegram_token
  read -r -p "Activer le modele vision Mistral ? [true]: " enable_vision
  read -r -p "Port web [48723]: " port
  port="${port:-48723}"
  enable_vision="$(normalize_bool "${enable_vision:-true}")"

  local enable_telegram="false"
  if [[ -n "$telegram_token" ]]; then
    enable_telegram="true"
  fi

  umask 077
  cat > .env <<EOF
MISTRAL_API_KEY=$mistral_key
MISTRAL_MODEL=mistral-large-latest
MISTRAL_MIN_SECONDS_BETWEEN_CALLS=20
MISTRAL_RATE_LIMIT_BACKOFF_SECONDS=60
MISTRAL_VISION_MODEL=pixtral-large-latest
ENABLE_VISION_MODEL=$enable_vision
VISION_EVERY_STEPS=3
TELEGRAM_BOT_TOKEN=$telegram_token
ENABLE_TELEGRAM=$enable_telegram
HOST=0.0.0.0
PORT=$port
DATABASE_PATH=data/agent_memory.sqlite3
SCREENSHOT_PATH=data/latest_screenshot.png
IMPORTANT_CAPTURE_DIR=data/captures
SCREENSHOT_BACKEND=auto
FILE_ACCESS_MODE=full
ALLOWED_FILE_ROOTS=
TERMINAL_WORKDIR=$HOME
SEARCH_ENGINE=duckduckgo
MAX_STEPS=50
MAX_RUNTIME_SECONDS=7200
MAX_RETRIES=3
LOOP_DELAY_SECONDS=1.0
MAX_REPEATED_ACTIONS=3
MAX_STAGNANT_OBSERVATIONS=3
CHECKPOINT_EVERY_STEPS=1
TERMINAL_TIMEOUT_SECONDS=30
BROWSER_HEADLESS=false
GMAIL_CREDENTIALS_FILE=credentials/gmail_credentials.json
GMAIL_TOKEN_FILE=credentials/gmail_token.json
GMAIL_SCOPE=https://www.googleapis.com/auth/gmail.modify
GMAIL_ENABLE_MODIFY=true
GMAIL_ALLOW_ARCHIVE=true
GMAIL_ALLOW_SEND=true
GMAIL_ALLOW_DELETE=true
SLACK_WEBHOOK_URL=
DISCORD_WEBHOOK_URL=
GITHUB_TOKEN=
GITHUB_REPO=
NOTION_TOKEN=
NOTION_PARENT_PAGE_ID=
CONNECTOR_TIMEOUT_SECONDS=30
EOF
  log ".env configure"
}

install_or_update() {
  log "Installation ou mise a jour"
  bash install.sh --no-env
  if [[ ! -f .env ]]; then
    configure_env
  fi
}

get_port() {
  if [[ -f .env ]]; then
    grep -E '^PORT=' .env | tail -n 1 | cut -d= -f2- || true
  fi
}

open_browser_later() {
  local port="${1:-48723}"
  (
    sleep 3
    if command -v xdg-open >/dev/null 2>&1; then
      xdg-open "http://127.0.0.1:$port" >/dev/null 2>&1 || true
    elif command -v gio >/dev/null 2>&1; then
      gio open "http://127.0.0.1:$port" >/dev/null 2>&1 || true
    fi
  ) &
}

repair_display_env() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    return 0
  fi
  if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    return 0
  fi
  if [[ -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=:0
    log "Affichage X11 detecte automatiquement: DISPLAY=:0"
  fi
}

launch_app() {
  if [[ ! -x .venv/bin/python ]]; then
    warn "Venv absent. Installation maintenant."
    install_or_update
  fi
  if [[ ! -f .env ]]; then
    configure_env
  fi

  repair_display_env

  if [[ "$(uname -s)" = "Linux" && -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    warn "Aucun affichage graphique detecte. Screenshot, OCR, souris et clavier ne fonctionneront pas."
    warn "Lance ce menu depuis ta session bureau, pas depuis un service SSH/headless."
  fi

  if ! command -v tesseract >/dev/null 2>&1; then
    warn "Tesseract OCR manque. Lance l'option 1 pour l'installer automatiquement."
    if command -v dnf >/dev/null 2>&1; then
      warn "Commande directe: sudo dnf install -y tesseract"
    fi
  fi

  local port
  port="$(get_port)"
  port="${port:-48723}"

  log "Lancement sur http://127.0.0.1:$port"
  open_browser_later "$port"
  .venv/bin/python main.py
}

menu() {
  while true; do
    clear || true
    printf '%s\n' "=========================================="
    printf '%s\n' "  $APP_NAME"
    printf '%s\n' "=========================================="
    printf '\n'
    printf '%s\n' "1. Installer ou mettre a jour"
    printf '%s\n' "2. Configurer les cles API"
    printf '%s\n' "3. Lancer l'application"
    printf '%s\n' "4. Creer le raccourci bureau/menu"
    printf '%s\n' "5. Quitter"
    printf '\n'
    read -r -p "Choix: " choice
    case "$choice" in
      1) install_or_update; pause ;;
      2) configure_env; pause ;;
      3) launch_app; pause ;;
      4) bash create_desktop_launcher.sh; pause ;;
      5) exit 0 ;;
      *) ;;
    esac
  done
}

menu
