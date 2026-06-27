# Changelog

## v0.3 — 2026-06-27

### New Features
- **Changeable thermal threshold**: New "Change Threshold" inline button lets you change the thermal alert temperature (0-110C) directly from chat. Bot sends a prompt, user enters a number, and the threshold updates instantly. Includes a Cancel button and 1-minute auto-timeout that deletes the prompt if no input is received.
- **Reset threshold button**: "Reset 90C" button next to "Change Threshold" instantly restores the default 90C threshold. Also cancels any pending threshold input.
- **`/cancel` command**: Cancel any pending threshold input from the command line.
- **`ALERT_THRESHOLD` now configurable via `.env`**: No need to edit `bot.py` — set `ALERT_THRESHOLD=90` in your `.env` file.

### Bug Fixes
- **Thermal alert flood fix**: When threshold was set very low and temperature was above it, thermal alerts would fire every cycle (delete + re-send), flooding the chat and making it impossible to interact with the threshold prompt. Thermal alerts now pause while threshold input is pending.

### Performance
- **Parallel API calls**: `editMessageText` for Bale and Telegram now run in parallel threads instead of sequentially, cutting update latency roughly in half.
- **Thermal alert sends parallelized**: Alert messages to both platforms are sent concurrently.
- **Reduced API timeout**: Dropped from 15s to 7s to fail faster on slow connections.
- **Faster main loop**: Sleep reduced from 0.5s to 0.15s, poll interval reduced from 5s to 2s for more responsive button/command handling.

### Changed
- Version bumped to v0.3
- Updated `/start` help text with `/cancel` command

---

## v0.2 (v6.0 in earlier tracking)

### Breaking Changes
- All user-facing text changed from Persian to English
- Removed `HOT_SKIP_RATE` config — thermal throttling is gone
- Update interval is now fixed at 3 seconds (was 2s with hot-skip logic)

### New Features
- **Thermal alerts**: When CPU or GPU exceeds 90C, a separate alert message is sent. If the component cools down on the next check, the alert is deleted. If it stays hot, the old alert is deleted and a new one is sent with updated temperature.
- **Restart Bot button**: New inline button to restart the bot's systemd service directly from chat.
- **Platform-aware formatting**: Telegram messages use `backtick` formatting for values. Bale messages use plain text since Bale does not support backtick rendering.

### Changed
- Volume buttons simplified to just 0% and 100% (was 25/50/75/100)
- Reduced emoji usage across all dialogs — cleaner, less robotic feel
- Removed emoji from button labels (e.g. "AnyDesk" instead of "🖥 AnyDesk")
- Docstrings and comments translated to English

### Removed
- Hot-skip rate limiting (no more `HOT_SKIP_RATE`, `HOT_TICK`)
- Slow update mode when CPU is hot — updates are always 3 seconds
- Excessive emoji in system messages

---

## v0.1 (v5.0 in earlier tracking)

- Full system monitor: CPU, RAM, GPU, processes
- Live terminal via PTY (bash shell in chat)
- Webcam and screenshot capture
- Volume control, screen lock, desktop notifications
- WiFi scanning and IP display
- AnyDesk remote launch
- Power options with confirmation (reboot/shutdown/sleep)
- Auto-throttling when CPU > 90C
- Bale + Telegram dual-platform support
- systemd user service with auto-start
