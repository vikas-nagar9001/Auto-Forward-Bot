import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables if .env file exists
load_dotenv()

# Manual configuration - These values can be modified directly
# They will be overridden by environment variables if set
class Config:
    # Telegram API Config (Required)
    API_ID = None  # Add your API_ID here if not using env var
    API_HASH = None  # Add your API_HASH here if not using env var
    BOT_TOKEN = None  # Add your BOT_TOKEN here if not using env var

    # MongoDB Config (Required)
    MONGO_URI = None  # Add your MONGO_URI here if not using env var
    DB_NAME = 'auto_forward_bot2'
    USERS_COLLECTION = 'users'
    GROUPS_COLLECTION = 'groups'

    # Web Server Config (Optional)
    PORT = 8080
    HOST = "0.0.0.0"

    # Admin Config (Optional)
    ADMIN_ID = 6080217547  # Add your ADMIN_ID here if not using env var




# Load environment variables if they exist, otherwise use manual config
class EnvConfig(Config):
    def __init__(self):
        # Telegram API Config
        self.API_ID = os.getenv('API_ID', Config.API_ID)
        self.API_HASH = os.getenv('API_HASH', Config.API_HASH)
        self.BOT_TOKEN = os.getenv('BOT_TOKEN', Config.BOT_TOKEN)

        # MongoDB Config
        self.MONGO_URI = os.getenv('MONGO_URI', Config.MONGO_URI)
        self.DB_NAME = os.getenv('DB_NAME', Config.DB_NAME)
        self.USERS_COLLECTION = os.getenv('USERS_COLLECTION', Config.USERS_COLLECTION)
        self.GROUPS_COLLECTION = os.getenv('GROUPS_COLLECTION', Config.GROUPS_COLLECTION)

        # Web Server Config
        self.PORT = int(os.getenv('PORT', Config.PORT))
        self.HOST = os.getenv('HOST', Config.HOST)

        # Admin Config
        self.ADMIN_ID = os.getenv('ADMIN_ID', Config.ADMIN_ID)

# Create config instance
config = EnvConfig()

def validate_config():
    """Validate that all required configuration values are set"""
    required_vars = {
        'API_ID': config.API_ID,
        'API_HASH': config.API_HASH,
        'BOT_TOKEN': config.BOT_TOKEN,
        'MONGO_URI': config.MONGO_URI
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        logger.error(
            f"Missing required configuration values: {', '.join(missing_vars)}\n"
            "Please either:\n"
            "1. Set them in environment variables\n"
            "2. Add them directly in the Config class in config.py"
        )
        return False
    
    return True

# Export all config values
API_ID = config.API_ID
API_HASH = config.API_HASH
BOT_TOKEN = config.BOT_TOKEN
MONGO_URI = config.MONGO_URI
DB_NAME = config.DB_NAME
USERS_COLLECTION = config.USERS_COLLECTION
GROUPS_COLLECTION = config.GROUPS_COLLECTION
PORT = config.PORT
HOST = config.HOST
ADMIN_ID = config.ADMIN_ID