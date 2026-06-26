# System Monitor v5 - Bale + Telegram Bot

> Monitor CPU temperature, usage, RAM, GPU, run terminal, take screenshots, control volume, lock screen, and more — from Bale and Telegram.

<p align="center">
  <a href="README-fa.md" style="color:#2196F3; font-size:18px; text-decoration:none; font-weight:bold;">
    📖 راهنمای فارسی — README-fa.md
  </a>
</p>

---

## ✨ Features

- **CPU**: Temperature, usage, load averages
- **RAM**: Used/total, swap
- **GPU**: Temperature & utilization (NVIDIA/AMD/Intel)
- **Processes**: Top CPU-consuming processes
- **Live Terminal**: Full interactive bash shell in chat (`/term`)
- **Screenshot** + **Webcam** capture
- **Volume control**, **Screen lock**, **Desktop notifications**
- **WiFi scanning**, **IP display**
- **AnyDesk** remote launch
- **Power options**: Reboot, Shutdown, Sleep (with confirmation)
- **Auto-throttling**: Slows updates when CPU > 90°C

---

## 📦 Requirements

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

## 🚀 Quick Install

```bash
cd ~/Documents/My-PJ/bale-cpu-alert
chmod +x start.sh
bash start.sh
```

The script checks dependencies, asks for tokens, creates `.env`, sets up systemd, and starts the bot.

---

## 📜 Helper Scripts

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
| `bash disable.sh` | ✅ | ✅ | ❌ |
| `bash disable.sh --remove-service` | ✅ | ✅ | ✅ |

---

## 🛠 Service Management

| Command | What it does |
|---------|--------------|
| `systemctl --user start bale-cpu-alert` | Start bot |
| `systemctl --user stop bale-cpu-alert` | Stop bot |
| `systemctl --user restart bale-cpu-alert` | Restart bot |
| `systemctl --user status bale-cpu-alert` | Check status |
| `journalctl --user -u bale-cpu-alert -f` | Live logs |
| `sudo loginctl enable-linger debian` | Keep running after logout |

---

## ⚙ Configuration

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
| `ALERT_THRESHOLD` | 90°C | CPU temp for slow mode |
| `INTERVAL_NORMAL` | 2s | Normal update interval |
| `HOT_SKIP_RATE` | 5 | Update every Nth cycle when hot |

---

## 📁 File Structure

```
bale-cpu-alert/
├── bot.py              # Main bot script
├── start.sh            # Installer & launcher
├── disable.sh          # Uninstall helper
├── README.md           # This file
├── README-fa.md        # Persian guide
├── .env                # Your tokens (excluded from git)
└── .env.example        # Example config
```

---

## 🔒 Security

- Keep `.env` private — **never commit it**
- Power commands (reboot/shutdown/sleep) require confirmation
- Terminal access = full shell access — restrict chat IDs
- Use separate bots for sensitive operations if needed
