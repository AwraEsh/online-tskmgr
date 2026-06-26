# System Monitor v5 - Bale + Telegram Bot

> مانیتورینگ سیستم: دمای CPU، RAM، GPU، ترمینال زنده، اسکرین‌شات، کنترل صدا و بیشتر — از طریق بله و تلگرام.

<p align="center">
  <a href="README.md" style="color:#2196F3; font-size:18px; text-decoration:none; font-weight:bold;">
    📖 English Version — README.md
  </a>
</p>

---

## ✨ قابلیت‌ها

- **CPU**: دما، درصد مصرف، لود سیستم
- **RAM**: مصرف/کل، swap
- **GPU**: دما و استفاده (NVIDIA/AMD/Intel)
- **پردازش‌ها**: پرمصرف‌ترین پردازش‌های CPU
- **ترمینال زنده**: شل bash تعاملی در چت (`/term`)
- **اسکرین‌شات** + **وب‌کم**
- **کنترل صدا**، **قفل صفحه**، **نوتیفیکیشن دسکتاپ**
- **اسکن WiFi**، **نمایش IP**
- **اجرا AnyDesk**
- **خاموش/ری‌استارت/اسلیپ** با تأیید
- **تنظیم خودکار**: کاهش سرعت آپدیت وقتی CPU > 90°C

---

## 📦 پیش‌نیازها

```bash
# پایتون
sudo apt install python3 python3-pil python3-xlib

# ابزارهای سیستمی
sudo apt install ffmpeg libnotify-bin network-manager pulseaudio-utils
```

### توکن‌های ربات

| پلتفرم | ساخت ربات | گرفتن Chat ID |
|---------|-----------|---------------|
| **Telegram** | [@BotFather](https://t.me/BotFather) | [@userinfobot](https://t.me/userinfobot) |
| **Bale** | [@BotFather](https://t.me/BotFather) | [@idfinderbot](https://t.me/idfinderbot) — بفرست `/MyID` |

---

## 🚀 نصب سریع

```bash
cd ~/Documents/My-PJ/bale-cpu-alert
chmod +x start.sh
bash start.sh
```

اسکریپت خودش پیش‌نیازها رو چک میکنه، توکن‌ها رو میپرسه، `.env` میسازه، سرویس systemd تنظیم میکنه و ربات رو اجرا میکنه.

---

## 🛠 مدیریت سرویس

| دستور | کارش |
|-------|------|
| `systemctl --user start bale-cpu-alert` | اجرای ربات |
| `systemctl --user stop bale-cpu-alert` | توقف ربات |
| `systemctl --user restart bale-cpu-alert` | ری‌استارت |
| `systemctl --user status bale-cpu-alert` | وضعیت |
| `journalctl --user -u bale-cpu-alert -f` | لاگ زنده |
| `sudo loginctl enable-linger debian` | اجرا بعد از خروج از سیستم |

---

## ⚙ تنظیمات

فایل `.env` رو تو پوشه پروژه ویرایش کن:

```ini
BALE_BOT_TOKEN=توکن بله
TG_BOT_TOKEN=توکن تلگرام
BALE_CHAT_ID=آیدی چت بله
TG_CHAT_ID=آیدی چت تلگرام
```

### تنظیمات ربات (در `bot.py`)

| متغیر | مقدار پیش‌فرض | توضیح |
|--------|--------------|------|
| `ALERT_THRESHOLD` | 90°C | آستانه دما برای حالت کند |
| `INTERVAL_NORMAL` | 2s | فاصله آپدیت عادی |
| `HOT_SKIP_RATE` | 5 | هر N سیکل آپدیت بشه وقتی داغه |

---

## 📁 ساختار فایل‌ها

```
bale-cpu-alert/
├── bot.py              # اسکریپت اصلی ربات
├── start.sh            # نصب‌کننده و اجراکننده
├── disable.sh          # حذف‌کننده سرویس
├── README.md           # راهنمای انگلیسی
├── README-fa.md        # این فایل (راهنمای فارسی)
├── .env                # توکن‌ها (از git خارج شده)
└── .env.example        # نمونه تنظیمات
```

---

## 🔒 امنیت

- فایل `.env` رو محرمانه نگه دار — **هرگز commit نکن**
- دستورات خاموش/ری‌استارت/اسلیپ نیاز به تأیید دارن
- ترمینال = دسترسی کامل شل — Chat ID محدود کن
- برای کارهای حساس از ربات‌های جداگانه استفاده کن
