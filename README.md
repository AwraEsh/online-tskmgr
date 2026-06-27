# System Monitor v0.3.3 — Bale + Telegram Bot

> Monitor CPU temperature, usage, RAM, GPU, run terminal, take screenshots, control volume, lock screen, and more — from Bale and Telegram.

<p align="center">
  <a href="README-fa.md" style="color:#2196F3; font-size:18px; text-decoration:none; font-weight:bold;">
    Persian Guide — README-fa.md
  </a>
</p>

---

## Features

- **CPU**: Temperature, usage, load averages
- **RAM**: Used/total, swap
- **GPU**: Temperature & utilization (NVIDIA/AMD/Intel)
- **Processes**: Top CPU & memory-consuming processes
- **Live Terminal**: Full interactive bash shell in chat (`/term`)
- **Screenshot** + **Webcam** capture
- **Volume control** (0% / 100%), **Screen lock**, **Desktop notifications**
- **WiFi scanning**, **IP display**
- **AnyDesk** remote launch
- **Power options**: Reboot, Shutdown, Sleep (with confirmation)
- **Restart Bot**: Restart the bot service from chat
- **Thermal alerts**: Separate alert message when CPU/GPU exceeds threshold, auto-deleted when cooled down
- **Changeable threshold**: Button to change thermal alert threshold (0-110C) from chat, with 1-minute timeout and cancel
- **Reset threshold**: "Reset 90C" button instantly restores the default 90C threshold
- **Smart suppression**: Thermal alerts pause while threshold input is pending to avoid flooding the chat

---

## Requirements

```bash
# Python
sudo apt install python3 python3-pil python3-xlib

# System tools
sudo apt install ffmpeg libnotify-bin network-manager pulseaudio-utils
```

### Bot Tokens

| Platform | Bot Father | Get Chat ID |
|----------|-----------|-------------|
| **Telegram** | [@BotFather](https://t.me/BotFather) | [@userinfobot](https://t.me/userinfobot) |
| **Bale** | [@BotFather](https://t.me/BotFather) | [@idfinderbot](https://t.me/idfinderbot) — send `/MyID` |

---

## Quick Install

```bash
cd ~/Documents/My-PJ/bale-cpu-alert
chmod +x start.sh
bash start.sh
```

The script checks dependencies, asks for tokens, creates `.env`, sets up systemd, and starts the bot.

---

## Helper Scripts

### `start.sh` — Install & Run

```bash
bash start.sh
```

Does everything in one go:
1. Checks and installs missing dependencies
2. Asks for bot tokens and chat IDs
3. Creates `.env` config file
4. Sets up systemd user service
5. Enables auto-start on boot
6. Starts the bot

### `disable.sh` — Stop & Disable

```bash
# Stop bot and disable auto-start (keeps service file)
bash disable.sh

# Stop bot, disable auto-start, AND remove service file completely
bash disable.sh --remove-service
```

| Command | Stops bot | Disables auto-start | Removes service file |
|---------|:---------:|:-------------------:|:--------------------:|
| `bash disable.sh` | Yes | Yes | No |
| `bash disable.sh --remove-service` | Yes | Yes | Yes |

---

## Service Management

| Command | What it does |
|---------|--------------|
| `systemctl --user start bale-cpu-alert` | Start bot |
| `systemctl --user stop bale-cpu-alert` | Stop bot |
| `systemctl --user restart bale-cpu-alert` | Restart bot |
| `systemctl --user status bale-cpu-alert` | Check status |
| `journalctl --user -u bale-cpu-alert -f` | Live logs |
| `sudo loginctl enable-linger debian` | Keep running after logout |

---

## Configuration

Edit `.env` in the project directory:

```ini
BALE_BOT_TOKEN=your_bale_token
TG_BOT_TOKEN=your_telegram_token
BALE_CHAT_ID=your_bale_chat_id
TG_CHAT_ID=your_telegram_chat_id
```

### Bot Settings (in `bot.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_THRESHOLD` | 90C | Temperature threshold for thermal alerts (changeable from .env or via bot button) |
| `INTERVAL_NORMAL` | 3s | Stats update interval |

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show help message |
| `/term` | Open live terminal |
| `/bye` | Close terminal |
| `/notif <text>` | Send desktop notification |
| `/vol <0-100>` | Set volume |
| `/cam` | Capture webcam photo |
| `/ss` | Take screenshot |
| `/ip` | Show IP addresses |
| `/wifi` | Scan WiFi networks |
| `/ad` | Launch AnyDesk |
| `/lock` | Lock screen |
| `/restart` | Restart bot service |
| `/cancel` | Cancel pending threshold input |

---

## File Structure

```
bale-cpu-alert/
├── bot.py              # Main bot script
├── start.sh            # Installer & launcher
├── disable.sh          # Uninstall helper
├── CHANGELOG.md        # Version history
├── README.md           # This file
├── README-fa.md        # Persian guide
├── .env                # Your tokens (excluded from git)
└── .env.example        # Example config
```

---

## Security

- Keep `.env` private — **never commit it**
- Power commands (reboot/shutdown/sleep) require confirmation
- Terminal access = full shell access — restrict chat IDs
- Use separate bots for sensitive operations if needed
