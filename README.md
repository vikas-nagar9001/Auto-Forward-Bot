# Auto Message Forwarder Bot

A Telegram bot that automates message forwarding to multiple groups with customizable intervals, interactive UI, and comprehensive management features.

## Key Features

- 🔄 Automated message forwarding with customizable intervals
- 👥 Multi-user support with individual configurations
- 🔐 Secure user authentication using Telethon session strings
- 📱 Interactive button-based interface for easy navigation
- ⚡ Real-time status monitoring and statistics
- ⏱️ Individual interval settings per group
- 📊 Detailed forwarding statistics and tracking
- 🛠️ Advanced group management features
- 💾 MongoDB integration for persistent storage

## Commands and Features


## Interactive Features

- 📋 Message selection interface
- 👥 Group selection with checkboxes
- ⏱️ Preset and custom intervals
- 📊 Real-time status updates
- 🔍 Detailed statistics view
- ⚡ Quick action shortcuts

## Setup Instructions

### Prerequisites
- Python 3.7 or higher
- MongoDB database
- Telegram API credentials

### Environment Variables
```
API_ID - Telegram API ID
API_HASH - Telegram API Hash
BOT_TOKEN - Telegram Bot Token
MONGO_URI - MongoDB Connection URI
PORT - Web Server Port (default: 8080)
```

### Installation Steps
1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables
4. Run the bot:
   ```bash
   python main.py
   ```

## Getting Started

1. Start a chat with the bot
2. Use `/register` and follow the interactive process
3. Add groups using `/addgroup` or the quick menu
4. Reply to any message with `/fwd` to start forwarding

## Security Features

- 🔐 Secure session-based authentication
- 🛡️ Permission validation for groups
- ✅ Input validation and error handling
- 🔒 Safe data storage practices

## Error Handling

The bot includes comprehensive error handling for:
- Invalid session strings
- Group permission issues
- Network connectivity problems
- Rate limiting and API restrictions
- Database connection issues

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.