#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/mistral-desktop-agent.desktop"

mkdir -p "$DESKTOP_DIR"
chmod +x "$PROJECT_DIR/launch.sh" 2>/dev/null || true

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Mistral Desktop Agent
Comment=Configurer et lancer l'agent autonome Mistral
Exec=bash "$PROJECT_DIR/launch.sh"
Path=$PROJECT_DIR
Terminal=true
Categories=Utility;Development;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo "Raccourci cree: $DESKTOP_FILE"
echo "Tu peux maintenant chercher 'Mistral Desktop Agent' dans le menu des applications."
