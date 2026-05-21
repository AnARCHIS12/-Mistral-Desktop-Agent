#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-https://github.com/AnARCHIS12/-Mistral-Desktop-Agent.git}"
ARCHIVE_URL="${ARCHIVE_URL:-https://github.com/AnARCHIS12/-Mistral-Desktop-Agent/archive/refs/heads/main.tar.gz}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/Mistral-Desktop-Agent}"
PASSTHROUGH_ARGS=()
ASSUME_YES=0
RUN_SERVER=0

bold="$(printf '\033[1m')"
green="$(printf '\033[32m')"
yellow="$(printf '\033[33m')"
red="$(printf '\033[31m')"
reset="$(printf '\033[0m')"

usage() {
  cat <<EOF
Mistral Desktop Agent bootstrap installer

Usage:
  curl -fsSL https://raw.githubusercontent.com/AnARCHIS12/-Mistral-Desktop-Agent/main/bootstrap.sh | bash

Options:
  -y, --yes              Passer --yes a install.sh
  --run                  Lancer le serveur apres installation
  --dir <path>           Dossier d'installation (defaut: $INSTALL_DIR)
  --                     Transmettre le reste des options a install.sh

Exemples:
  curl -fsSL https://raw.githubusercontent.com/AnARCHIS12/-Mistral-Desktop-Agent/main/bootstrap.sh | bash
  curl -fsSL https://raw.githubusercontent.com/AnARCHIS12/-Mistral-Desktop-Agent/main/bootstrap.sh | bash -s -- --yes
  curl -fsSL https://raw.githubusercontent.com/AnARCHIS12/-Mistral-Desktop-Agent/main/bootstrap.sh | bash -s -- --dir ~/.local/share/mistral-agent -- --port 8001
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

parse_args() {
  local passthrough=0
  while [[ $# -gt 0 ]]; do
    if [[ "$passthrough" -eq 1 ]]; then
      PASSTHROUGH_ARGS+=("$1")
      shift
      continue
    fi

    case "$1" in
      -y|--yes)
        ASSUME_YES=1
        shift
        ;;
      --run)
        RUN_SERVER=1
        shift
        ;;
      --dir)
        INSTALL_DIR="${2:-}"
        [[ -n "$INSTALL_DIR" ]] || fail "--dir attend une valeur"
        shift 2
        ;;
      --)
        passthrough=1
        shift
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

download_with_git() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Mise a jour du depot existant: $INSTALL_DIR"
    git -C "$INSTALL_DIR" pull --ff-only
    return 0
  fi

  if [[ -e "$INSTALL_DIR" ]]; then
    warn "$INSTALL_DIR existe deja sans depot git. Les fichiers seront conserves."
  else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    log "Clonage du depot: $REPO_URL"
    git clone "$REPO_URL" "$INSTALL_DIR"
    return 0
  fi

  log "Synchronisation par git dans le dossier existant"
  git clone "$REPO_URL" "$INSTALL_DIR.tmp"
  cp -R "$INSTALL_DIR.tmp"/. "$INSTALL_DIR"/
  rm -rf "$INSTALL_DIR.tmp"
}

download_with_tarball() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' RETURN

  log "Telechargement de l'archive GitHub"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$ARCHIVE_URL" -o "$tmp_dir/source.tar.gz"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$tmp_dir/source.tar.gz" "$ARCHIVE_URL"
  else
    fail "curl, wget ou git est requis pour telecharger le projet"
  fi

  mkdir -p "$tmp_dir/source" "$INSTALL_DIR"
  tar -xzf "$tmp_dir/source.tar.gz" -C "$tmp_dir/source" --strip-components=1
  cp -R "$tmp_dir/source"/. "$INSTALL_DIR"/
}

install_project() {
  if command -v git >/dev/null 2>&1; then
    download_with_git
  else
    download_with_tarball
  fi

  chmod +x "$INSTALL_DIR/install.sh" 2>/dev/null || true

  local args=()
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    args+=(--yes)
  fi
  if [[ "$RUN_SERVER" -eq 1 ]]; then
    args+=(--run)
  fi
  args+=("${PASSTHROUGH_ARGS[@]}")

  log "Lancement de install.sh"
  cd "$INSTALL_DIR"
  bash install.sh "${args[@]}"
}

main() {
  parse_args "$@"
  printf '%s\n' "${bold}Mistral Desktop Agent${reset}"
  printf '%s\n' "Destination: $INSTALL_DIR"
  install_project
}

main "$@"
