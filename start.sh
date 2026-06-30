#!/usr/bin/env bash
set -e

# ==============================================================
# System Monitor v0.2 — Installer & Launcher
# Bale + Telegram CPU Alert Bot
# ==============================================================
# Checks prerequisites, sets up config, creates systemd service,
# and starts the bot.
# Usage: bash start.sh
# ==============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERR]${NC}   $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_PY="$SCRIPT_DIR/bot.py"
ENV_FILE="$SCRIPT_DIR/.env"
SERVICE_NAME="bale-cpu-alert"
SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME.service"

# ── 1. Check Python ───────────────────────────────────────────
info "Checking Python installation..."
if ! command -v python3 &>/dev/null; then
    err "Python 3 is not installed. Install it with:"
    err "  sudo apt install python3"
    exit 1
fi
ok "Python 3 found: $(python3 --version)"

# ── 2. Check & install dependencies ───────────────────────────
info "Checking system dependencies..."

DEPS_MISSING=()

# Python packages
python3 -c "from Xlib import display" 2>/dev/null || DEPS_MISSING+=("python3-xlib")
python3 -c "from PIL import Image" 2>/dev/null || DEPS_MISSING+=("python3-pil")

# System tools
command -v ffmpeg &>/dev/null || DEPS_MISSING+=("ffmpeg")
command -v notify-send &>/dev/null || DEPS_MISSING+=("libnotify-bin")
command -v nmcli &>/dev/null || DEPS_MISSING+=("network-manager")
command -v pactl &>/dev/null || DEPS_MISSING+=("pulseaudio-utils")

if [ ${#DEPS_MISSING[@]} -gt 0 ]; then
    warn "Missing dependencies: ${DEPS_MISSING[*]}"
    echo -e "${YELLOW}Attempting to install with apt...${NC}"
    sudo apt update
    sudo apt install -y "${DEPS_MISSING[@]}"
    ok "Dependencies installed."
else
    ok "All system dependencies found."
fi

# ── 3. Check/Collect config ────────────────────────────────────
info "Checking configuration..."

# Load existing .env if present
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE" 2>/dev/null || true
fi

# Check if bot.py uses os.environ (it should!)
if ! grep -q 'os.environ.get("BALE_BOT_TOKEN"' "$BOT_PY" 2>/dev/null; then
    warn "bot.py is not using os.environ for tokens!"
    warn "Please ensure bot.py lines 15-19 use os.environ.get()"
    echo ""
fi

# Get current values from .env or defaults
CURRENT_BALE=$(grep '^BALE_BOT_TOKEN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '" ' || echo "")
CURRENT_TG=$(grep '^TG_BOT_TOKEN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '" ' || echo "")
CURRENT_BALE_CHAT=$(grep '^BALE_CHAT_ID=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '" ' || echo "")
CURRENT_TG_CHAT=$(grep '^TG_CHAT_ID=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '" ' || echo "")

# Ask for tokens if any are missing
NEED_INPUT=false

if [ -z "$CURRENT_BALE" ]; then
    NEED_INPUT=true
fi
if [ -z "$CURRENT_TG" ]; then
    NEED_INPUT=true
fi
if [ -z "$CURRENT_BALE_CHAT" ]; then
    NEED_INPUT=true
fi
if [ -z "$CURRENT_TG_CHAT" ]; then
    NEED_INPUT=true
fi

if [ "$NEED_INPUT" = true ]; then
    echo ""
    echo -e "${CYAN}── Token Setup ──────────────────────────────────────${NC}"
    echo "Enter your bot tokens. Leave empty to skip (but bot won't work)."
    echo ""

    read -rp "Bale Bot Token [$CURRENT_BALE]: " INPUT_BALE
    read -rp "Telegram Bot Token [$CURRENT_TG]: " INPUT_TG
    read -rp "Bale Chat ID [$CURRENT_BALE_CHAT]: " INPUT_BALE_CHAT
    read -rp "Telegram Chat ID [$CURRENT_TG_CHAT]: " INPUT_TG_CHAT

    BALE="${INPUT_BALE:-$CURRENT_BALE}"
    TG="${INPUT_TG:-$CURRENT_TG}"
    BALE_CHAT="${INPUT_BALE_CHAT:-$CURRENT_BALE_CHAT}"
    TG_CHAT="${INPUT_TG_CHAT:-$CURRENT_TG_CHAT}"

    # Write .env
    cat > "$ENV_FILE" <<EOF
# Bot Configuration
# Get these from @BotFather on Telegram / Bale
BALE_BOT_TOKEN=$BALE
TG_BOT_TOKEN=$TG
BALE_CHAT_ID=$BALE_CHAT
TG_CHAT_ID=$TG_CHAT
EOF
    chmod 600 "$ENV_FILE"
    ok "Configuration saved to .env"
else
    ok "Configuration already exists in .env"
fi

# ── 4. Verify bot.py uses env vars ──────────────────────────────
info "Verifying bot.py configuration..."

# Check if bot.py reads from environment variables
if grep -q 'os.environ.get("BALE_BOT_TOKEN"' "$BOT_PY" && \
   grep -q 'os.environ.get("TG_BOT_TOKEN"' "$BOT_PY" && \
   grep -q 'os.environ.get("BALE_CHAT_ID"' "$BOT_PY" && \
   grep -q 'os.environ.get("TG_CHAT_ID"' "$BOT_PY"; then
    ok "bot.py correctly uses environment variables"
else
    err "bot.py does NOT use environment variables!"
    err "Please edit bot.py lines 15-19 to use os.environ.get()"
    exit 1
fi

# ── 5. Create systemd service ─────────────────────────────────
info "Setting up systemd user service..."

mkdir -p "$HOME/.config/systemd/user"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Bale CPU Temperature Monitor Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $BOT_PY
Restart=always
RestartSec=3
EnvironmentFile=$ENV_FILE
WorkingDirectory=$SCRIPT_DIR

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME" 2>/dev/null
ok "Service file created at $SERVICE_FILE"

# ── 6. Start ──────────────────────────────────────────────────
info "Starting the bot..."
systemctl --user restart "$SERVICE_NAME"
sleep 2

if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    ok "Bot is running!"
    echo ""
    echo -e "${GREEN}── Bot Status ──────────────────────────────────────────${NC}"
    systemctl --user status "$SERVICE_NAME" --no-pager | head -12
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo "  restart:  systemctl --user restart $SERVICE_NAME"
    echo "  stop:     systemctl --user stop $SERVICE_NAME"
    echo "  logs:     journalctl --user -u $SERVICE_NAME -f"
    echo "  status:   systemctl --user status $SERVICE_NAME"
else
    err "Bot failed to start. Check logs: journalctl --user -u $SERVICE_NAME -e"
    exit 1
fi
