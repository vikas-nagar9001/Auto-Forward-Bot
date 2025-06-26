# Auto Message Forwarder Bot

A powerful Telegram bot that automates message forwarding to multiple groups with advanced group management, bulk operations, and comprehensive user-friendly features.

## Key Features

- 🔄 **Automated Message Forwarding** with customizable intervals (5 seconds to 24 hours)
- 👥 **Multi-user Support** with individual configurations and isolated data
- 🔐 **Secure Authentication** using Telethon session strings with validation
- 📱 **Interactive UI** with button-based navigation and real-time feedback
- ⚡ **Real-time Monitoring** with live status updates and statistics
- 🛠️ **Advanced Group Management** with multiple input formats and validation
- 📥 **Bulk Group Operations** - Add up to 10 groups simultaneously
- � **Flexible Group Input** - Support for IDs, usernames, and t.me links
- 📊 **Comprehensive Statistics** with detailed forwarding tracking
- � **Robust Data Storage** with MongoDB integration and error handling
- 🚀 **Production Ready** with comprehensive error handling and logging

## Commands and Features

### Core Commands
- `/start` - Welcome message and quick start guide
- `/register` - Interactive session registration with validation
- `/help` - Comprehensive command reference and usage guide

### Group Management
- `/addgroup` - Add a single group with interactive validation
- `/bulkaddgroups` - Add multiple groups (up to 10) in one operation
- `/mygroups` - View and manage all configured groups
- `/removegroup` - Remove groups with confirmation prompts

### Message Forwarding
- `/fwd` - Reply to any message to start forwarding with interval selection
- `/status` - View active forwards, statistics, and system status
- `/stop` - Stop specific forwards or all forwarding activities

### Advanced Features
- **Smart Group Input**: Accepts group IDs, usernames (@groupname), and t.me links
- **Bulk Operations**: Process multiple groups with comprehensive result reporting
- **Real-time Validation**: Instant feedback on group permissions and access
- **Duplicate Detection**: Automatic prevention of duplicate group additions
- **Error Recovery**: Robust error handling with user-friendly messages
- **Session Management**: Automatic session validation and renewal prompts


## Interactive Features

- 📋 **Message Selection Interface** - Choose messages with context preview
- 👥 **Advanced Group Management** - Add, remove, and organize groups easily
- 📥 **Bulk Group Addition** - Add multiple groups with format validation
- ⏱️ **Flexible Intervals** - Preset options (5s-24h) and custom intervals
- 📊 **Real-time Dashboard** - Live status updates and comprehensive statistics
- 🔍 **Detailed Analytics** - Success rates, error tracking, and performance metrics
- ⚡ **Quick Actions** - One-click shortcuts for common operations
- 🛠️ **Group Validation** - Automatic permission checking and error reporting
- 🔄 **Session Recovery** - Automatic session renewal and validation prompts
- 📱 **Mobile-Friendly UI** - Optimized button layouts and responsive design

## Group Input Formats

The bot supports multiple ways to add groups for maximum flexibility:

### Single Group Addition (`/addgroup`)
- **Group ID**: `-1001234567890` (recommended for private groups)
- **Username**: `@mygroupname` or `mygroupname` (for public groups)
- **t.me Links**: `t.me/mygroupname` or `https://t.me/mygroupname`

### Bulk Group Addition (`/bulkaddgroups`)
Add up to 10 groups in one operation with mixed formats:
```
-1001234567890
@cryptogroup
https://t.me/tradingchat
technews
-1001234567892
```

### Features of Group Management
- ✅ **Automatic Validation** - Checks permissions and access before adding
- ✅ **Duplicate Prevention** - Prevents adding the same group twice
- ✅ **Error Reporting** - Clear feedback on what succeeded or failed
- ✅ **Username Resolution** - Automatically converts usernames to group IDs
- ✅ **Link Parsing** - Extracts usernames from various t.me link formats
- ✅ **Batch Processing** - Handles multiple groups with individual result tracking

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

# Admin Config (Optional)
ADMIN_ID = 11223455  # Add your ADMIN_ID here if not using env var

Bot Startup Notifications: When the bot starts up, if ADMIN_ID is configured, it sends a detailed status notification to that user with information about:
MongoDB connection status
Handler initialization status
Web server status
Overall bot readiness
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

### Quick Start with Script (Linux/macOS)
For convenience, you can use the provided run script:
```bash
chmod +x run.sh
./run.sh
```
This script will:
- ✅ Check Python version compatibility
- 📦 Install all required dependencies
- 🔧 Verify configuration
- 🚀 Start the bot automatically

## Getting Started

### Quick Start Guide
1. **Start the Bot**: Send `/start` to get a welcome message and overview
2. **Register Your Account**: Use `/register` and follow the interactive session setup
3. **Add Groups**: 
   - Single group: `/addgroup` → Enter group ID, username, or t.me link
   - Multiple groups: `/bulkaddgroups` → Send a list of groups (one per line)
4. **Start Forwarding**: Reply to any message with `/fwd` and select target groups + interval

### Detailed Workflow
1. **Session Registration**:
   - Get your session string from a Telegram client
   - Use `/register` and paste the session string
   - Bot validates the session and confirms setup

2. **Group Configuration**:
   - Join target groups with your account first
   - Add groups using flexible input formats
   - Bot validates permissions and access automatically

3. **Message Forwarding**:
   - Reply to any message with `/fwd`
   - Select target groups from your configured list
   - Choose forwarding interval (5 seconds to 24 hours)
   - Monitor progress with `/status`

### Tips for Best Results
- 🔑 **Group Access**: Ensure your account has joined all target groups
- 🛡️ **Permissions**: Make sure you can send messages in target groups
- ⏱️ **Intervals**: Use appropriate delays to avoid rate limiting
- 📊 **Monitoring**: Check `/status` regularly for forwarding health
- 🔄 **Updates**: Restart forwarding if you add new groups

## Security Features

- 🔐 **Secure Session Management** - Encrypted session storage with validation
- 🛡️ **Permission Validation** - Automatic checking of group access and bot permissions
- ✅ **Input Sanitization** - Comprehensive validation of all user inputs
- 🔒 **Data Isolation** - User data completely separated and secured
- 🚫 **Rate Limiting Protection** - Built-in delays to prevent API restrictions
- � **Session Recovery** - Automatic detection and recovery from expired sessions
- 📝 **Audit Logging** - Comprehensive logging for debugging and monitoring
- 🛠️ **Error Boundaries** - Graceful error handling prevents system crashes

## Error Handling

The bot includes comprehensive error handling for:

### Connection Issues
- **Network Problems**: Automatic retry with exponential backoff
- **API Rate Limits**: Built-in delays and queue management
- **Session Expiry**: Automatic detection with user notification
- **Database Connectivity**: Connection pooling and failover handling

### User Input Validation
- **Invalid Group IDs**: Clear error messages with correction guidance
- **Permission Issues**: Detailed feedback on required permissions
- **Duplicate Groups**: Prevention with user-friendly notifications
- **Format Errors**: Helpful examples and format guides

### System Reliability
- **Background Task Management**: Proper cleanup and resource management
- **Memory Management**: Efficient data structures and garbage collection
- **Concurrent Operations**: Thread-safe operations and data consistency
- **Graceful Shutdown**: Clean termination of all active processes

### User Experience
- **Clear Error Messages**: Human-readable error descriptions
- **Recovery Suggestions**: Actionable steps to resolve issues
- **Progress Feedback**: Real-time updates on operation status
- **Help Integration**: Context-sensitive help and guidance

## Advanced Usage

### Bulk Group Management
The bot supports adding multiple groups simultaneously for efficiency:

```
/bulkaddgroups

Example input:
-1001234567890
@cryptogroup
https://t.me/tradingchat
technews
t.me/announcements
```

**Result Breakdown**:
- ✅ **Successfully Added**: Groups that were validated and added
- ❌ **Invalid Groups**: Groups with permission or access issues
- ⚠️ **Duplicates**: Groups already in your list (skipped)
- 🔍 **Parsing Errors**: Invalid formats with correction suggestions
- 📊 **Summary Statistics**: Complete breakdown of the operation

### Forwarding Strategies
- **High Volume**: Use longer intervals (30+ seconds) for many groups
- **Real-time**: Use shorter intervals (5-10 seconds) for urgent messages
- **Mixed Groups**: Different intervals for different group types
- **Load Balancing**: Stagger forwarding times to distribute load

### Monitoring and Maintenance
- **Regular Status Checks**: Use `/status` to monitor forwarding health
- **Performance Optimization**: Adjust intervals based on success rates
- **Group Cleanup**: Remove inactive or problematic groups
- **Session Renewal**: Update sessions before they expire

## Contributing

We welcome contributions! Here's how to get involved:

1. **Fork the Repository**: Create your own copy for development
2. **Create Feature Branches**: Work on features in isolated branches
3. **Follow Code Standards**: Maintain consistent coding style
4. **Add Tests**: Ensure new features include appropriate tests
5. **Submit Pull Requests**: Provide clear descriptions of changes

### Development Setup
```bash
git clone https://github.com/your-username/Auto-Forward-Bot.git
cd Auto-Forward-Bot
pip install -r requirements.txt
cp config.py.example config.py  # Configure your settings
python main.py
```

### Areas for Contribution
- 🔧 **Feature Development**: New functionality and improvements
- 🐛 **Bug Fixes**: Issue resolution and stability improvements
- 📚 **Documentation**: README updates and code documentation
- 🧪 **Testing**: Unit tests and integration testing
- 🎨 **UI/UX**: Interface improvements and user experience

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Support

- 📖 **Documentation**: Check this README for comprehensive guidance
- 🐛 **Bug Reports**: Use GitHub Issues for bug reporting
- 💡 **Feature Requests**: Submit enhancement ideas via GitHub Issues
- 📧 **Contact**: Reach out for questions or collaboration

---

**Made with ❤️ for the Telegram community**