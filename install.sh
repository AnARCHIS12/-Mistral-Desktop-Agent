#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="Mistral Desktop Agent"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-}"
PORT="${PORT:-48723}"
HOST="${HOST:-0.0.0.0}"
MISTRAL_MODEL="${MISTRAL_MODEL:-mistral-large-latest}"
INSTALL_PLAYWRIGHT=1
INSTALL_SYSTEM_PACKAGES=1
WRITE_ENV=1
RUN_SERVER=0
ASSUME_YES=0

bold="$(printf '\033[1m')"
green="$(printf '\033[32m')"
yellow="$(printf '\033[33m')"
red="$(printf '\033[31m')"
reset="$(printf '\033[0m')"

usage() {
  cat <<EOF
$APP_NAME installer

Usage:
  ./install.sh [options]

Options:
  -y, --yes              Mode non interactif, accepte les valeurs par defaut
  --no-env               Ne pas creer/modifier .env
  --skip-playwright      Ne pas installer Chromium Playwright
  --skip-system-packages Ne pas installer les paquets systeme comme Tesseract OCR
  --run                  Lancer le serveur apres installation
  --host <host>          Host FastAPI (defaut: $HOST)
  --port <port>          Port FastAPI (defaut: $PORT)
  --python <path>        Python a utiliser (doit etre >= 3.11)
  -h, --help             Afficher cette aide

Variables utiles:
  MISTRAL_API_KEY, TELEGRAM_BOT_TOKEN, ENABLE_TELEGRAM, PYTHON_BIN, VENV_DIR
EOF
}

log() {
  printf '%s\n' "${green}==>${reset} $*"
}

warn() {
  printf '%s\n' "${yellow}Warning:${reset} $*"
}

fail() {
  printf '%s\n' "${red}Error:${reset} $*" >&2
  exit 1
}

confirm() {
  local prompt="$1"
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    return 0
  fi
  read -r -p "$prompt [Y/n] " answer
  case "${answer:-Y}" in
    y|Y|yes|YES|Yes) return 0 ;;
    *) return 1 ;;
  esac
}

prompt_secret() {
  local label="$1"
  local default="${2:-}"
  local value=""
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    printf '%s' "$default"
    return 0
  fi
  read -r -s -p "$label" value
  printf '\n' >&2
  printf '%s' "${value:-$default}"
}

prompt_text() {
  local label="$1"
  local default="${2:-}"
  local value=""
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    printf '%s' "$default"
    return 0
  fi
  read -r -p "$label" value
  printf '%s' "${value:-$default}"
}

normalize_bool() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    y|yes|oui|o|true|1|on) printf '%s' "true" ;;
    n|no|non|false|0|off) printf '%s' "false" ;;
    *) printf '%s' "$1" ;;
  esac
}

version_ge_311() {
  "$1" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

find_python() {
  if [[ -n "$PYTHON_BIN" ]]; then
    command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python introuvable: $PYTHON_BIN"
    version_ge_311 "$PYTHON_BIN" || fail "$PYTHON_BIN doit etre en version 3.11+"
    printf '%s' "$PYTHON_BIN"
    return 0
  fi

  local candidate
  for candidate in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && version_ge_311 "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done
  fail "Python 3.11+ est requis. Installe python3.11, python3.12 ou python3.13."
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -y|--yes)
        ASSUME_YES=1
        shift
        ;;
      --no-env)
        WRITE_ENV=0
        shift
        ;;
      --skip-playwright)
        INSTALL_PLAYWRIGHT=0
        shift
        ;;
      --skip-system-packages)
        INSTALL_SYSTEM_PACKAGES=0
        shift
        ;;
      --run)
        RUN_SERVER=1
        shift
        ;;
      --host)
        HOST="${2:-}"
        [[ -n "$HOST" ]] || fail "--host attend une valeur"
        shift 2
        ;;
      --port)
        PORT="${2:-}"
        [[ -n "$PORT" ]] || fail "--port attend une valeur"
        shift 2
        ;;
      --python)
        PYTHON_BIN="${2:-}"
        [[ -n "$PYTHON_BIN" ]] || fail "--python attend une valeur"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Option inconnue: $1"
        ;;
    esac
  done
}

create_env_file() {
  local env_file="$PROJECT_DIR/.env"
  if [[ "$WRITE_ENV" -eq 0 ]]; then
    log "Configuration .env ignoree"
    return 0
  fi

  if [[ -f "$env_file" ]] && ! confirm ".env existe deja. Le mettre a jour ?"; then
    log ".env conserve tel quel"
    return 0
  fi

  local mistral_key="${MISTRAL_API_KEY:-}"
  local telegram_token="${TELEGRAM_BOT_TOKEN:-}"
  local enable_telegram="${ENABLE_TELEGRAM:-true}"
  local enable_vision="${ENABLE_VISION_MODEL:-true}"

  if [[ -z "$mistral_key" ]]; then
    mistral_key="$(prompt_secret "Cle MISTRAL_API_KEY (laisser vide pour plus tard): ")"
  fi
  if [[ -z "$telegram_token" ]]; then
    telegram_token="$(prompt_secret "Token TELEGRAM_BOT_TOKEN optionnel (laisser vide pour desactiver): ")"
  fi
  if [[ -z "$telegram_token" ]]; then
    enable_telegram="false"
  else
    enable_telegram="$(prompt_text "Activer Telegram ? [true/false] (${enable_telegram}): " "$enable_telegram")"
  fi
  enable_vision="$(normalize_bool "$(prompt_text "Activer le modele vision Mistral ? [true/false] (${enable_vision}): " "$enable_vision")")"

  umask 077
  cat > "$env_file" <<EOF
MISTRAL_API_KEY=$mistral_key
MISTRAL_MODEL=$MISTRAL_MODEL
MISTRAL_MIN_SECONDS_BETWEEN_CALLS=20
MISTRAL_RATE_LIMIT_BACKOFF_SECONDS=60
MISTRAL_VISION_MODEL=pixtral-large-latest
ENABLE_VISION_MODEL=$enable_vision
VISION_EVERY_STEPS=3
TELEGRAM_BOT_TOKEN=$telegram_token
ENABLE_TELEGRAM=$enable_telegram
HOST=$HOST
PORT=$PORT
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

sudo_prefix() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    return 0
  fi
  if command -v sudo >/dev/null 2>&1; then
    printf '%s' "sudo"
    return 0
  fi
  return 1
}

install_tesseract() {
  if command -v tesseract >/dev/null 2>&1; then
    log "Tesseract detecte: $(tesseract --version | head -n 1)"
    return 0
  fi

  if [[ "$INSTALL_SYSTEM_PACKAGES" -eq 0 ]]; then
    warn "Installation systeme ignoree. Tesseract OCR n'est pas installe."
    return 0
  fi

  if ! confirm "Installer Tesseract OCR maintenant ?"; then
    warn "Tesseract OCR non installe. L'OCR restera indisponible."
    return 0
  fi

  local sudo_cmd=""
  sudo_cmd="$(sudo_prefix || true)"
  if [[ "${EUID:-$(id -u)}" -ne 0 && -z "$sudo_cmd" ]]; then
    warn "sudo est requis pour installer Tesseract automatiquement."
    warn "Commande manuelle Fedora/RHEL: sudo dnf install -y tesseract"
    return 0
  fi

  if command -v dnf >/dev/null 2>&1; then
    log "Installation OCR: ${sudo_cmd:+$sudo_cmd }dnf install -y tesseract"
    ${sudo_cmd:+$sudo_cmd} dnf install -y tesseract
  elif command -v apt-get >/dev/null 2>&1; then
    log "Installation OCR: ${sudo_cmd:+$sudo_cmd }apt-get install -y tesseract-ocr"
    ${sudo_cmd:+$sudo_cmd} apt-get update
    ${sudo_cmd:+$sudo_cmd} apt-get install -y tesseract-ocr
  elif command -v pacman >/dev/null 2>&1; then
    log "Installation OCR: ${sudo_cmd:+$sudo_cmd }pacman -S --noconfirm tesseract"
    ${sudo_cmd:+$sudo_cmd} pacman -S --noconfirm tesseract
  elif command -v zypper >/dev/null 2>&1; then
    log "Installation OCR: ${sudo_cmd:+$sudo_cmd }zypper install -y tesseract-ocr"
    ${sudo_cmd:+$sudo_cmd} zypper install -y tesseract-ocr
  else
    warn "Gestionnaire de paquets non reconnu. Installe Tesseract manuellement."
    return 0
  fi

  if command -v tesseract >/dev/null 2>&1; then
    log "Tesseract installe: $(tesseract --version | head -n 1)"
  else
    warn "Tesseract ne semble toujours pas disponible dans PATH."
  fi
}

install_screenshot_tools() {
  if command -v gnome-screenshot >/dev/null 2>&1 || command -v grim >/dev/null 2>&1 || command -v spectacle >/dev/null 2>&1 || command -v scrot >/dev/null 2>&1; then
    log "Outil de capture detecte"
    return 0
  fi

  if [[ "$INSTALL_SYSTEM_PACKAGES" -eq 0 ]]; then
    warn "Installation systeme ignoree. Aucun outil de capture Wayland/X11 detecte."
    return 0
  fi

  if ! confirm "Installer les outils de capture ecran maintenant ?"; then
    warn "Aucun outil de capture supplementaire installe."
    return 0
  fi

  local sudo_cmd=""
  sudo_cmd="$(sudo_prefix || true)"
  if [[ "${EUID:-$(id -u)}" -ne 0 && -z "$sudo_cmd" ]]; then
    warn "sudo est requis pour installer les outils de capture automatiquement."
    return 0
  fi

  if command -v dnf >/dev/null 2>&1; then
    log "Installation capture: ${sudo_cmd:+$sudo_cmd }dnf install -y gnome-screenshot grim scrot"
    ${sudo_cmd:+$sudo_cmd} dnf install -y gnome-screenshot grim scrot
  elif command -v apt-get >/dev/null 2>&1; then
    log "Installation capture: ${sudo_cmd:+$sudo_cmd }apt-get install -y gnome-screenshot grim scrot"
    ${sudo_cmd:+$sudo_cmd} apt-get update
    ${sudo_cmd:+$sudo_cmd} apt-get install -y gnome-screenshot grim scrot
  elif command -v pacman >/dev/null 2>&1; then
    log "Installation capture: ${sudo_cmd:+$sudo_cmd }pacman -S --noconfirm gnome-screenshot grim scrot"
    ${sudo_cmd:+$sudo_cmd} pacman -S --noconfirm gnome-screenshot grim scrot
  elif command -v zypper >/dev/null 2>&1; then
    log "Installation capture: ${sudo_cmd:+$sudo_cmd }zypper install -y gnome-screenshot grim scrot"
    ${sudo_cmd:+$sudo_cmd} zypper install -y gnome-screenshot grim scrot
  else
    warn "Gestionnaire de paquets non reconnu. Installe gnome-screenshot ou grim manuellement."
  fi
}

check_system_tools() {
  if ! command -v tesseract >/dev/null 2>&1; then
    warn "Tesseract OCR n'est pas installe. OCR indisponible tant que tesseract-ocr manque."
    if command -v apt-get >/dev/null 2>&1; then
      warn "Commande suggeree: sudo apt-get install tesseract-ocr"
    elif command -v dnf >/dev/null 2>&1; then
      warn "Commande suggeree: sudo dnf install tesseract"
    elif command -v pacman >/dev/null 2>&1; then
      warn "Commande suggeree: sudo pacman -S tesseract"
    fi
  else
    log "Tesseract detecte: $(tesseract --version | head -n 1)"
  fi
}

install_python_deps() {
  local python="$1"
  log "Python detecte: $("$python" --version)"
  log "Creation/mise a jour du venv: $VENV_DIR"
  "$python" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
}

install_playwright() {
  if [[ "$INSTALL_PLAYWRIGHT" -eq 0 ]]; then
    log "Installation Playwright ignoree"
    return 0
  fi
  log "Installation de Chromium pour Playwright"
  "$VENV_DIR/bin/python" -m playwright install chromium
}

verify_app() {
  log "Verification des imports applicatifs"
  (
    cd "$PROJECT_DIR"
    ENABLE_TELEGRAM=false MISTRAL_API_KEY="${MISTRAL_API_KEY:-dummy}" "$VENV_DIR/bin/python" - <<'PY'
from main import app
print(app.title)
PY
  )
}

run_server() {
  if [[ "$RUN_SERVER" -eq 0 ]]; then
    return 0
  fi
  log "Lancement du serveur sur http://127.0.0.1:$PORT"
  cd "$PROJECT_DIR"
  exec "$VENV_DIR/bin/python" main.py
}

main() {
  parse_args "$@"
  printf '%s\n' "${bold}$APP_NAME${reset}"
  printf '%s\n' "Projet: $PROJECT_DIR"

  local python
  python="$(find_python)"

  mkdir -p "$PROJECT_DIR/data"
  install_python_deps "$python"
  install_playwright
  install_tesseract
  install_screenshot_tools
  create_env_file
  check_system_tools
  verify_app

  log "Installation terminee"
  printf '\n%s\n' "Commandes utiles:"
  printf '  %s\n' "source .venv/bin/activate"
  printf '  %s\n' "python main.py"
  printf '  %s\n' "ouvrir http://127.0.0.1:$PORT"

  run_server
}

main "$@"
