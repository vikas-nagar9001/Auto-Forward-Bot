# Auto Message Forwarder Bot

🚀 Automatically send your messages to multiple Telegram groups at once!

✅ Forward messages to up to 10 groups instantly  
✅ Customizable delays (5 seconds to 24 hours)  
✅ Bulk group operations and smart validation  
✅ Real-time monitoring and statistics  

Start with `/register` to begin.

## Features

- 🔄 **Automated Forwarding** with customizable intervals
- 👥 **Multi-user Support** with isolated user data
- 🔐 **Secure Authentication** using Telethon session strings
- 📱 **Interactive UI** with button-based navigation
- 📊 **Real-time Monitoring** and comprehensive statistics
- 🛠️ **Smart Group Management** - supports IDs, usernames, and t.me links
- � **Bulk Operations** - add/manage multiple groups simultaneously
- 🚀 **Production Ready** with robust error handling

## Commands

- `/start` - Welcome and quick start guide
- `/register` - Setup your Telegram session
- `/help` - Command reference
- `/addgroup` - Add a single group
- `/bulkaddgroups` - Add multiple groups (up to 10)
- `/mygroups` - View and manage your groups
- `/removegroup` - Remove groups
- `/fwd` - Forward a message (reply to any message)
- `/status` - View active forwards and statistics
- `/stop` - Stop forwarding activities

## Group Input Formats

**Single Group (`/addgroup`)**:
- Group ID: `-1001234567890`
- Username: `@mygroupname`
- t.me link: `https://t.me/mygroupname`

**Bulk Groups (`/bulkaddgroups`)** - one per line:
```
-1001234567890
@cryptogroup
https://t.me/tradingchat
```

## Setup

### Prerequisites
- Python 3.7+
- MongoDB database
- Telegram API credentials

### Environment Variables
```
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
MONGO_URI=mongodb://localhost:27017/
PORT=8080
ADMIN_ID=123456789  # Optional: for startup notifications
```

### Installation
```bash
git clone https://github.com/your-username/Auto-Forward-Bot.git
cd Auto-Forward-Bot
pip install -r requirements.txt
python main.py
```

### Quick Start (Linux/macOS)
```bash
chmod +x run.sh
./run.sh
```

## Getting Started

1. **Register**: Use `/register` and provide your Telegram session string
2. **Add Groups**: Use `/addgroup` or `/bulkaddgroups` to add target groups
3. **Forward Messages**: Reply to any message with `/fwd`, select groups and interval
4. **Monitor**: Use `/status` to track forwarding progress

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request with clear description

## License

MIT License - see [LICENSE](LICENSE) file.

## Support

- 🐛 **Bug Reports**: GitHub Issues
- 💡 **Feature Requests**: GitHub Issues
- 📧 **Contact**: Open an issue for questions

---

**Made with ❤️ for the Telegram community**