from flask import Flask
from threading import Thread
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import asyncio
import os
import time

# Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return 'Forwarder bot is running on Railway!'

# Telegram config
API_ID = 24732393
API_HASH = 'ac0d702e4ec6b2d5c232cb5a7e0b7619'
SESSION_STRING = '1BVtsOKEBu0cxC_XxLDXiTEljOcEf5JO6MT46QiP7-hHFXo41Y_nOmmHFxL1p0qioT_qRHx26y_uKPXQ_xJK12Sf9fY2Bs6NYjqd1rc66SCAftE1isM8Lzif7icJzFQuxSNdC8Hc9r6D6IfE0gX9kOqZ907XRk5roXKIlT3j6wgHKSx47ALFvsugQQsvgM8XSl-ndpn_OsvaD67pFSdaDp8oNGG_yNUBWzeENjPZHWxP-GNaO8U4mpFJHxynNdk1gk2hh5Tm3TQyM-GQIJHEWYkyjFiiXhpkCgWcqFXnL5uCFvgno857XO0Fj07TKuBbQ_cqfq1AP2sTyZNUBy7utZCZtDw7ml_A='

# Dictionary to store group IDs and their intervals (in seconds)
GROUP_SETTINGS = {
    -1001581718139: {'interval': 20},  # 1 minute default usa
    -1001331854632: {'interval': 60},  # 1 minute default virtual
    -1001619638916: {'interval': 4000},# 1 minute default clone
    -1001243384244: {'interval': 17280}, # free whatsapp urdu
    -1002393876754 : {'interval': 20000}, # numro virtual
    -1001656474954 : {'interval': 20000}, # numro virtual
}

DELAY_BETWEEN_FORWARDS = 3  # seconds
DEFAULT_INTERVAL = 60  # 1 minute default interval

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Global variables to store the forwarded message and tasks
message_to_forward = None
forwarding_tasks = {}
# Dictionary to track when each group was last forwarded to
last_forward_time = {}

@client.on(events.NewMessage(pattern=r'^/fwd(?: (\d+))?$'))
async def manual_fwd(event):
    global message_to_forward, forwarding_tasks

    interval = event.pattern_match.group(1)
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg.text:
            message_to_forward = reply_msg.text

            try:
                # Set the same interval for all groups if specified
                if interval:
                    interval_seconds = int(interval) * 60
                    for group_id in GROUP_SETTINGS:
                        GROUP_SETTINGS[group_id]['interval'] = interval_seconds
                    await event.reply(f"✅ Message scheduled to be forwarded every {interval} minute(s) to all groups.")
                else:
                    await event.reply(f"✅ Message scheduled to be forwarded using each group's configured interval.")
            except ValueError:
                await event.reply("❌ Invalid interval. Please use a number (e.g., /fwd 2).")
                return

            # Cancel any existing forwarding tasks
            for group_id, task in forwarding_tasks.items():
                if task and not task.done():
                    task.cancel()
            
            # Create a new forwarding task
            asyncio.create_task(schedule_forward_message())
        else:
            await event.reply("❌ Replied message has no text.")
    else:
        await event.reply("❌ Please reply to the message you want to forward using /fwd <interval>.")

@client.on(events.NewMessage(pattern=r'^/stopfwd$'))
async def stop_forwarding(event):
    global message_to_forward, forwarding_tasks
    message_to_forward = None
    
    # Cancel all forwarding tasks
    for group_id, task in forwarding_tasks.items():
        if task and not task.done():
            task.cancel()
    
    forwarding_tasks = {}
    await event.reply("🛑 Forwarding stopped for all groups.")

@client.on(events.NewMessage(pattern=r'^/status$'))
async def check_status(event):
    if message_to_forward:
        status_message = "✅ Currently forwarding to groups with these intervals:\n"
        for group_id, settings in GROUP_SETTINGS.items():
            minutes = settings['interval'] // 60
            status_message += f"- Group {group_id}: every {minutes} minute(s)\n"
        await event.reply(status_message)
    else:
        await event.reply("❌ No message is currently being forwarded.")

@client.on(events.NewMessage(pattern=r'^/setinterval (\d+) (-?\d+)$'))
async def set_interval(event):
    try:
        minutes, group_id = event.pattern_match.groups()
        minutes = int(minutes)
        group_id = int(group_id)
        
        if group_id in GROUP_SETTINGS:
            GROUP_SETTINGS[group_id]['interval'] = minutes * 60
            await event.reply(f"✅ Interval for group {group_id} set to {minutes} minute(s).")
        else:
            await event.reply(f"❌ Group ID {group_id} not found in the configured groups.")
    except ValueError:
        await event.reply("❌ Invalid format. Use /setinterval <minutes> <group_id>")

@client.on(events.NewMessage(pattern=r'^/addgroup (-?\d+) (\d+)$'))
async def add_group(event):
    try:
        group_id, minutes = event.pattern_match.groups()
        group_id = int(group_id)
        minutes = int(minutes)
        
        GROUP_SETTINGS[group_id] = {'interval': minutes * 60}
        await event.reply(f"✅ Added group {group_id} with forwarding interval of {minutes} minute(s).")
    except ValueError:
        await event.reply("❌ Invalid format. Use /addgroup <group_id> <minutes>")

@client.on(events.NewMessage(pattern=r'^/removegroup (-?\d+)$'))
async def remove_group(event):
    try:
        group_id = int(event.pattern_match.group(1))
        
        if group_id in GROUP_SETTINGS:
            del GROUP_SETTINGS[group_id]
            # Also cancel any active task for this group
            if group_id in forwarding_tasks and not forwarding_tasks[group_id].done():
                forwarding_tasks[group_id].cancel()
                del forwarding_tasks[group_id]
            await event.reply(f"✅ Removed group {group_id} from forwarding list.")
        else:
            await event.reply(f"❌ Group ID {group_id} not found in the configured groups.")
    except ValueError:
        await event.reply("❌ Invalid format. Use /removegroup <group_id>")

async def forward_to_group(group_id):
    global message_to_forward, last_forward_time
    try:
        interval = GROUP_SETTINGS[group_id]['interval']
        while message_to_forward:
            try:
                await client.send_message(group_id, message_to_forward)
                last_forward_time[group_id] = time.time()
            except Exception as e:
                print(f"Failed to send message to group {group_id}: {e}")
            
            # Wait for this group's specific interval
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        # Handle task cancellation gracefully
        pass

async def schedule_forward_message():
    global message_to_forward, forwarding_tasks, last_forward_time
    
    # Initialize the last forward time for each group
    for group_id in GROUP_SETTINGS:
        last_forward_time[group_id] = 0
        
    # Start a separate task for each group
    for group_id in GROUP_SETTINGS:
        if group_id not in forwarding_tasks or forwarding_tasks[group_id].done():
            forwarding_tasks[group_id] = asyncio.create_task(forward_to_group(group_id))
            # Add a small delay between starting tasks to avoid rate limits
            await asyncio.sleep(0.5)

async def telethon_main():
    await client.start()
    print("Telethon client started.")
    await client.run_until_disconnected()

def run_telethon():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(telethon_main())

if __name__ == "__main__":
    Thread(target=run_telethon).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
