# System Monitor v5 - Bale + Telegram Bot 

> **A comprehensive system monitoring bot for Bale and Telegram**
> 
> Monitor CPU temperature, usage, RAM, GPU, run live terminal, take screenshots, control volume, lock screen, and more - all from your messenger!

---

## ✨ Features

### 📊 System Monitoring
- **CPU**: Temperature, usage percentage, load averages (1/5/15 min)
- **RAM**: Used/total memory, percentage, swap usage
- **GPU**: Temperature and utilization (NVIDIA, AMD, Intel)
- **Processes**: Top 7 CPU-consuming processes
- **Uptime**: System uptime display
- **Auto-throttling**: Reduces update frequency when CPU is hot (>90°C)

### 🎮 Interactive Commands

| Command | Description |
|---------|-------------|
| `/start` | Show help and available commands |
| `/term` | Open a **live bash terminal** in your chat |
| `/bye` | Close the terminal session |
| `/ad` | Launch AnyDesk for remote access |
| `/lock` | Lock the screen |
| `/notif <text>` | Send a desktop notification |
| `/cam` | Capture and send a photo from webcam |
| `/ss` | Take and send a screenshot |
| `/ip` | Show public and private IP addresses |
| `/wifi` | List available WiFi networks with signal strength |
| `/vol <0-100>` | Set system volume (e.g., `/vol 75`) |

### ⚡ Quick Actions (Inline Buttons)
- **AnyDesk** - Remote access
- **Lock** - Lock the screen
- **Webcam** - Capture photo
- **Screenshot** - Capture screen
- **IP** - Show IP addresses
- **WiFi** - List networks
- **Volume** - 25%, 50%, 75%, 100%
- **Power** - Reboot, Shutdown, Sleep (with confirmation)

### 🔥 Special Features
- **Live PTY Terminal**: Full interactive bash shell in your chat
- **Dual Platform**: Works simultaneously on Bale and Telegram
- **Persistent**: Runs as a systemd service, auto-restarts on crash
- **Real-time Updates**: Stats refresh every 2 seconds (5x slower when CPU >90°C)
- **Security**: Power commands require confirmation

---

## 📦 Requirements

### System Dependencies

```bash
# Python packages
sudo apt install python3 python3-pil python3-xlib

# System tools
sudo apt install ffmpeg libnotify-bin network-manager pulseaudio-utils
```

| Package | Purpose |
|---------|---------|
| `python3` | Python runtime |
| `python3-pil` | Image processing (screenshots) |
| `python3-xlib` | X11 access (screenshots) |
| `ffmpeg` | Webcam capture |
| `libnotify-bin` | Desktop notifications (`/notif`) |
| `network-manager` | WiFi scanning (`/wifi`) |
| `pulseaudio-utils` | Volume control (`/vol`) |

### Bot Tokens

You need bot tokens from both platforms:

1. **Telegram**: Talk to [@BotFather](https://t.me/BotFather) on Telegram
   - Create a new bot with `/newbot`
   - Copy the **Bot Token**
   - To get your **Chat ID**, send a message to [@userinfobot](https://t.me/userinfobot) on Telegram

2. **Bale**: Talk to [@BotFather](https://t.me/BotFather) on Bale
   - Create a new bot with `/newbot`
   - Copy the **Bot Token**
   - To get your **Chat ID**, send `/MyID` to [@idfinderbot](https://t.me/idfinderbot) on Bale

---

## 🚀 Installation & Setup

### Method 1: Quick Start (Recommended)

```bash
# Navigate to project directory
cd ~/Documents/My-PJ/bale-cpu-alert

# Make start.sh executable
chmod +x start.sh

# Run the installer (will ask for tokens and install dependencies)
bash start.sh
```

The script will:
1. ✅ Check and install missing dependencies
2. ✅ Ask for your bot tokens and chat IDs
3. ✅ Create `.env` configuration file
4. ✅ Set up systemd user service
5. ✅ Start the bot automatically

### Method 2: Manual Setup

#### 1. Clone/Download the project

```bash
mkdir -p ~/Documents/My-PJ/bale-cpu-alert
cd ~/Documents/My-PJ/bale-cpu-alert
# Download bot.py and other files here
```

#### 2. Install dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pil python3-xlib ffmpeg libnotify-bin network-manager pulseaudio-utils
```

#### 3. Configure tokens

Create `.env` file:

```bash
nano ~/.config/bale-cpu-alert/.env
```

Add your tokens:

```ini
# Bot Configuration
# Get these from @BotFather on Telegram / Bale
BALE_BOT_TOKEN=your_bale_bot_token_here
TG_BOT_TOKEN=your_telegram_bot_token_here
BALE_CHAT_ID=your_bale_chat_id_here
TG_CHAT_ID=your_telegram_chat_id_here
```

**Important**: The bot.py **MUST** use environment variables. Ensure lines 15-19 look like:

```python
BALE_TOKEN  = os.environ.get("BALE_BOT_TOKEN", "")
BALE_CHAT   = os.environ.get("BALE_CHAT_ID", "")
TG_TOKEN    = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT     = os.environ.get("TG_CHAT_ID", "")
```

#### 4. Create systemd service

```bash
mkdir -p ~/.config/systemd/user

nano ~/.config/systemd/user/bale-cpu-alert.service
```

Paste:

```ini
[Unit]
Description=Bale CPU Temperature Monitor Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/debian/Documents/My-PJ/bale-cpu-alert/bot.py
Restart=always
RestartSec=10
EnvironmentFile=/home/debian/Documents/My-PJ/bale-cpu-alert/.env
WorkingDirectory=/home/debian/Documents/My-PJ/bale-cpu-alert

[Install]
WantedBy=default.target
```

#### 5. Enable and start the service

```bash
# Reload systemd
systemctl --user daemon-reload

# Enable to start on boot
systemctl --user enable bale-cpu-alert

# Start the bot
systemctl --user start bale-cpu-alert

# Check status
systemctl --user status bale-cpu-alert
```

---

## 🎛️ Service Management

### Using systemctl (Manual)

| Command | Description |
|---------|-------------|
| `systemctl --user start bale-cpu-alert` | Start the bot |
| `systemctl --user stop bale-cpu-alert` | Stop the bot |
| `systemctl --user restart bale-cpu-alert` | Restart the bot |
| `systemctl --user status bale-cpu-alert` | Check bot status |
| `systemctl --user enable bale-cpu-alert` | Enable auto-start on boot |
| `systemctl --user disable bale-cpu-alert` | Disable auto-start |
| `journalctl --user -u bale-cpu-alert -f` | View live logs |
| `journalctl --user -u bale-cpu-alert -e` | View error logs |

### Using Scripts (Recommended)

| Script | Description |
|--------|-------------|
| `bash start.sh` | Install dependencies, setup config, create service, enable auto-start, and start bot |
| `bash disable.sh` | Stop bot, disable auto-start on boot |
| `bash disable.sh --remove-service` | Stop bot, disable auto-start, AND remove service file completely |

### Enable lingering (run after logout)

By default, user services stop when you log out. To keep the bot running:

```bash
# Enable lingering for your user
sudo loginctl enable-linger debian

# Check if enabled
loginctl show-user debian | grep Linger
# Should show: Linger=yes
```

---

## 📝 Configuration

### Environment Variables

Edit `.env` file in the project directory:

```ini
# Required - Bot tokens
BALE_BOT_TOKEN=your_bale_bot_token
TG_BOT_TOKEN=your_telegram_bot_token

# Required - Your chat IDs (where bot sends messages)
BALE_CHAT_ID=your_bale_chat_id
TG_CHAT_ID=your_telegram_chat_id

# Optional - Alert settings (edit in bot.py)
# ALERT_THRESHOLD=90      # CPU temp threshold for slow updates
# INTERVAL_NORMAL=2       # Normal update interval (seconds)
# HOT_SKIP_RATE=5         # Update every N cycles when hot
```

### Bot Settings (bot.py)

Edit the configuration section in `bot.py`:

```python
ALERT_THRESHOLD = 90    # °C - When CPU is hotter than this, updates slow down
INTERVAL_NORMAL = 2     # Seconds between normal updates
HOT_SKIP_RATE   = 5     # Update every 5th cycle when CPU > ALERT_THRESHOLD
```

---

## 🔧 Troubleshooting

### Bot won't start

```bash
# Check logs
journalctl --user -u bale-cpu-alert -e

# Common issues:
# 1. Missing dependencies - run: bash start.sh
# 2. Wrong tokens in .env - verify your tokens
# 3. .env file permissions - run: chmod 600 .env
# 4. systemd not reloaded - run: systemctl --user daemon-reload
```

### Screenshot not working

```bash
# Check if X11 is available
 echo $DISPLAY
# Should output: :0 or :1

# If not set, try:
export DISPLAY=:0

# Or edit bot.py line 463 to use correct display
```

### Webcam not working

```bash
# Check if webcam is detected
ls /dev/video*

# Test with ffmpeg
ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 /tmp/test.jpg
```

### Terminal not working

The bot uses PTY for live terminal. Ensure:
- Your user has PTY access
- The bot is running with proper permissions
- No firewall blocking the connection

### "One of the environment variables is missing"

This means your `.env` file is not being loaded. Check:

```bash
# Verify .env exists and has correct permissions
ls -la /home/debian/Documents/My-PJ/bale-cpu-alert/.env

# Verify systemd service has EnvironmentFile
cat ~/.config/systemd/user/bale-cpu-alert.service | grep EnvironmentFile

# Restart after fixing
systemctl --user daemon-reload
systemctl --user restart bale-cpu-alert
```

---

## 📚 File Structure

```
bale-cpu-alert/
├── bot.py              # Main bot script
├── start.sh            # Installer and launcher
├── README.md           # This file
├── .env                # Configuration (tokens)
└── .env.example        # Example configuration
```

---

## 🎯 Usage Examples

### Start a terminal session
```
You: /term
Bot: 💻 Terminal (bash)
     به شل متصل شدی. هر دستوری بزن برات اجرا میکنم.
     /bye برای خروج.

You: ls -la
Bot: 💻 Terminal
     
     total 24
     drwxr-xr-x 2 debian debian 4096 Jun 27 01:00 .
     drwxr-xr-x 3 debian debian 4096 Jun 27 00:59 ..
     -rw-r--r-- 1 debian debian  123 Jun 27 01:00 .env
     ...

You: /bye
Bot: 👋 ترمینال بسته شد.
```

### Check system status
```
Bot automatically sends:
💻 **System Monitor** · 4C
⏱ 2d 3h 45m
▬▬▬▬▬▬▬▬▬▬▬▬▬
🖥 **CPU** 🟢`[██████████]` 45.2°C
   ⚡ `45.2%` ▓▓▓▓▓▓▓▓░░
   📊 Load: `1.23 / 1.45 / 1.32`

💾 **RAM** 🟢 `6.2/15.5GB` · `40.5%` ▓▓▓▓▓▓░░░░

🎮 **GPU** (NVIDIA) · 🌡65°C ⚡35%
```

### Control the system
```
You: /vol 50
Bot: 🔊 صدا روی 50% تنظیم شد.

You: /lock
Bot: 🔒 صفحه قفل شد!

You: /ip
Bot: 🌐 **IP Address**
▬▬▬▬▬▬▬▬▬▬▬▬▬
🏠 **Private:**
`192.168.1.100`

🌍 **Public:**
`123.45.67.89`
```

---

## 🔒 Security Notes

1. **Keep your tokens secret** - Never commit `.env` to version control
2. **Power commands require confirmation** - Reboot/Shutdown/Sleep need explicit confirmation
3. **Terminal access** - Anyone with access to the bot can run commands on your system
4. **Use at your own risk** - This bot has full system access

### Recommended security measures:

1. **Restrict chat IDs**: Only allow your own chat IDs in the bot
2. **Use separate bots**: One for monitoring, one for control commands
3. **Disable dangerous commands**: Comment out power commands in `bot.py` if not needed
4. **Regular updates**: Keep your system and dependencies updated

---

## 📈 Performance

- **CPU Usage**: ~0.5-2% (idle), up to 5% during screenshot/webcam
- **Memory Usage**: ~50-100MB
- **Update Frequency**: Every 2 seconds (normal), every 10 seconds when CPU >90°C
- **Network**: Minimal (only API calls to Bale/Telegram)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is **free to use** for personal and educational purposes.

---

## 🙏 Acknowledgments

- **Bale.ai** - Persian messaging platform
- **Telegram** - Messaging platform
- **Python** - The programming language
- **Systemd** - Service management

---

## 📞 Support

For issues, questions, or suggestions:
- Check the **Troubleshooting** section above
- Review the logs with `journalctl --user -u bale-cpu-alert -f`
- Ensure all dependencies are installed

---

*Made with ❤️ for system monitoring enthusiasts*
*Version: 5.0 | Last Updated: June 2026*
