"""
# Auto Message Forwarder Bot

A Telegram bot that allows users to automatically forward messages to multiple groups at specified intervals.

## Features

- Multi-user support with individual configurations
- User registration with Session String
- Add and manage multiple destination groups
- Customizable forwarding intervals for each group
- Simple command interface
- MongoDB integration for persistent storage

## Commands

- `/start` - welcome message and about the bot or how to use the bot
- `/help` - Show available commands
- `/register <session_string>` - Register your Telegram account
- `/addgroup <group_id> <interval_minutes>` - Add a group to forward messages to
- `/removegroup <group_id>` - Remove a group
- `/setinterval <minutes> <group_id>` - Set forwarding interval for a group
- `/fwd <optional_interval_minutes>` - Forward a message (reply to a message)
- `/stopfwd` - Stop forwarding messages
- `/status` - Check forwarding status
- `/mygroups` - List your configured groups
- `/myaccount` - View your account information
- `/unregister` - Unregister your account

## Setup

### Prerequisites

- Python 3.7+
- MongoDB database
- Telegram API credentials

### Environment Variables

- `API_ID` - Telegram api id (provided by Telegram)
- `API_HASH` - Telegram api Hash (provided by Telegram)
- `BOT_TOKEN` - Telegram bot token (provided by BotFather)
- `MONGO_URI` - MongoDB connection string
- `PORT` - Port for the Flask web server (optional, defaults to 8080)

### Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables
4. Run the bot: `python main.py`

## Getting Started

1. Start a chat with the bot.
2. Register your Telegram account using the `/register <session_string>` command.
3. Add groups using the `/addgroup` command.
4. Reply to a message with `/fwd` to start forwarding.

## How to Get Your Telegram API Credentials

1. Visit [https://my.telegram.org/auth](https://my.telegram.org/auth) and log in.
2. Go to "API development tools".
3. Create a new application.
4. Note your API ID and API Hash.
5. Use a session string generator to create your session string.
## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.