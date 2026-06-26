#!/usr/bin/env bash
set -e

# ==============================================================
# System Monitor v5 — Service Disabler & Cleanup
# ==============================================================
# Stops the bot service, disables auto-start, and optionally
# removes the service file completely.
# Usage: bash disable.sh [--remove-service]
#   --remove-service: Also delete the service file
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

SERVICE_NAME="bale-cpu-alert"
SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME.service"

# Parse arguments
REMOVE_SERVICE=false
for arg in "$@"; do
    case "$arg" in
        --remove-service)
            REMOVE_SERVICE=true
            ;;
    esac
done

# ── 1. Stop the service ─────────────────────────────────────────
info "Stopping $SERVICE_NAME service..."
if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl --user stop "$SERVICE_NAME"
    ok "Service stopped."
else
    warn "Service is not currently running."
fi

# ── 2. Disable auto-start ────────────────────────────────────────
info "Disabling auto-start on boot..."
if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl --user disable "$SERVICE_NAME"
    ok "Auto-start disabled. Bot will NOT start on next boot."
else
    warn "Service was not enabled for auto-start."
fi

# ── 3. Reload systemd ───────────────────────────────────────────
info "Reloading systemd user daemon..."
systemctl --user daemon-reload
ok "Systemd reloaded."

# ── 4. (Optional) Remove service file ────────────────────────────
if [ "$REMOVE_SERVICE" = true ]; then
    info "Removing service file..."
    if [ -f "$SERVICE_FILE" ]; then
        rm -f "$SERVICE_FILE"
        ok "Service file removed: $SERVICE_FILE"
    else
        warn "Service file not found: $SERVICE_FILE"
    fi
    
    # Reload again after removal
    systemctl --user daemon-reload
    ok "Systemd reloaded after service removal."
fi

# ── 5. Show status ───────────────────────────────────────────────
echo ""
echo -e "${CYAN}── Current Status ──────────────────────────────────────────${NC}"
if [ -f "$SERVICE_FILE" ]; then
    echo "  Service file: EXISTS at $SERVICE_FILE"
else
    echo "  Service file: REMOVED"
fi

if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "  Auto-start: ENABLED"
else
    echo "  Auto-start: DISABLED"
fi

if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "  Running: YES"
else
    echo "  Running: NO"
fi

echo ""
echo -e "${CYAN}To re-enable the bot, run:${NC}"
echo "  bash start.sh"
