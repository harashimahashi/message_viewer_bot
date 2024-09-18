from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from telegram.error import RetryAfter
from telegram.constants import ParseMode
from telethon import TelegramClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
import traceback
import asyncio
import os
import random
import redis
import re

class SensitiveDataFormatter(logging.Formatter):
    def __init__(self, token, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        self.pattern = re.compile(re.escape(token), re.IGNORECASE) if token else None

    def format(self, record):
        original_msg = super().format(record)
        if self.pattern:
            return self.pattern.sub("[REDACTED]", original_msg)
        return original_msg

load_dotenv()

bot_token = os.getenv("BOT_TOKEN")
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
redis_host = os.getenv("REDIS_HOST")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()

formatter = SensitiveDataFormatter(bot_token, '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger.addHandler(handler)

httpx_logger = logging.getLogger('httpx')
httpx_logger.setLevel(logging.INFO)
httpx_logger.addHandler(handler)

telegram_logger = logging.getLogger('telegram')
telegram_logger.setLevel(logging.INFO)
telegram_logger.addHandler(handler)

client = TelegramClient('bot_session', api_id, api_hash)
redis_client = redis.StrictRedis(host=redis_host, port=6379, db=0, decode_responses=True)

chat_cooldowns = {}

COOLDOWN_DURATION = timedelta(seconds=15)

MAX_USES_BEFORE_COOLDOWN = 2
REDIS_TTL=300

async def forward_command(update: Update, context: CallbackContext) -> None:
    args = context.args

    try:
        if len(args) == 1:
            source_chat = update.message.chat_id
            message_id = int(args[0])
        elif len(args) == 2:
            source_chat = args[0]
            message_id = int(args[1])
        else:
            await update.message.reply_text('Usage: /forward [<source_chat>] <message_id>')
            return
    except ValueError:
        await update.message.reply_text('The message ID must be an integer.')
        return

    await client.start()

    try:
        # Resolve the source chat if it's not already an ID
        if len(args) == 2:
            entity = await client.get_entity(source_chat)
            source_chat = "-100" + str(entity.id)

        forwarded_message = await context.bot.forward_message(
            chat_id=update.message.chat_id,
            from_chat_id=source_chat,
            message_id=message_id
        )

        redis_key = f"{source_chat}_{forwarded_message.message_id}"
        redis_client.set(redis_key, message_id, ex=REDIS_TTL)

    except Exception as e:
        logger.error(f"Error forwarding message: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"An error occurred: {str(e)}")
    finally:
        await client.disconnect();

async def forward_reply_command(update: Update, context: CallbackContext) -> None:
    if not update.message.reply_to_message:
        await update.message.reply_text('You need to reply to a message.')
        return

    reply_to_message_id = update.message.reply_to_message.message_id

    redis_key = f"{update.message.chat_id}_{reply_to_message_id}"
    original_message_id = redis_client.get(redis_key)
    if original_message_id:
        reply_to_message_id = int(original_message_id)

    await client.start()

    try:
        # Fetch the message the replied-to message is replying to
        message = await client.get_messages(update.message.chat_id, ids=reply_to_message_id)

        if message.reply_to:
            original_message_id = message.reply_to.reply_to_msg_id
            source_chat_id = message.chat_id

            forwarded_message = await context.bot.forward_message(
                chat_id=update.message.chat_id,
                from_chat_id=source_chat_id,
                message_id=original_message_id
            )

            redis_key = f"{source_chat_id}_{forwarded_message.message_id}"
            redis_client.set(redis_key, original_message_id, ex=REDIS_TTL)

        else:
            await update.message.reply_text('The replied-to message is not a reply to another message.')
    except Exception as e:
        logger.error(f"Error processing forward_reply: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"An error occurred: {str(e)}")
    finally:
        await client.disconnect()

async def forward_message_with_replies(chat_id, from_chat_id, message_id, context: CallbackContext):
    # Get the message
    message = await client.get_messages(from_chat_id, ids=message_id)

    # If the message is a reply to another message
    if message.reply_to:
        original_message_id = message.reply_to.reply_to_msg_id

        # Recursively forward the original message
        await forward_message_with_replies(chat_id, from_chat_id, original_message_id, context)

    # Forward the current message
    await context.bot.forward_message(
        chat_id=chat_id,
        from_chat_id=from_chat_id,
        message_id=message_id
    )

async def forward_thread_command(update: Update, context: CallbackContext) -> None:
    args = context.args
    user_chat_id = update.message.from_user.id

    try:
        # Check if the command is used as a reply
        if update.message.reply_to_message:
            source_chat_id = update.message.chat_id
            message_id = update.message.reply_to_message.message_id
        elif len(args) == 1:
            source_chat_id = update.message.chat_id
            message_id = int(args[0])
        elif len(args) == 2:
            source_chat_id = args[0]
            message_id = int(args[1])
        else:
            await update.message.reply_text('Usage: /forward_thread [[<source_chat>] <message_id>]')
            return
    except ValueError:
        await update.message.reply_text('The message ID must be an integer.')
        return

    await client.start()

    try:
        # Notify the user that messages are being sent to their private chat
        if update.message.chat.type != 'private':
            await update.message.reply_text("Messages forwarded to the private chat")

        if len(args) == 2:
            entity = await client.get_entity(source_chat_id)
            source_chat_id = int("-100" + str(entity.id))

        redis_key = f"{source_chat_id}_{message_id}"
        original_message_id = redis_client.get(redis_key)
        if original_message_id:
            message_id = int(original_message_id)

        await forward_message_with_replies(user_chat_id, source_chat_id, message_id, context);

    except Exception as e:
        logger.error(f"Error forwarding message thread: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"An error occurred: {str(e)}")
    finally:
        await client.disconnect()

async def forward_n_command(update: Update, context: CallbackContext) -> None:
    args = context.args
    user_chat_id = update.message.from_user.id

    try:
        if len(args) == 2:
            source_chat_id = update.message.chat_id
            message_id = int(args[0])
            count = int(args[1])
        elif len(args) == 3:
            source_chat_id = args[0]
            message_id = int(args[1])
            count = int(args[2])
        else:
            await update.message.reply_text('Usage: /forward_n [<source_chat>] <message_id> <count>')
            return
    except ValueError:
        await update.message.reply_text('Incorrect format.')
        return
    
    if count < 0:
        await update.message.reply_text('Incorrect format.')
        return
    elif count > 100:
        await update.message.reply_text('Too many messages! The maximum is 100.')
        return       

    await client.start()

    try:
        # Notify the user that messages are being sent to their private chat
        if update.message.chat.type != 'private':
            await update.message.reply_text("Messages forwarded to the private chat")

        if len(args) == 3:
            entity = await client.get_entity(source_chat_id)
            source_chat_id = int("-100" + str(entity.id))

        redis_key = f"{source_chat_id}_{message_id}"
        original_message_id = redis_client.get(redis_key)
        if original_message_id:
            message_id = int(original_message_id)

        for i in range(message_id, message_id + count + 1):
            try:
                await context.bot.forward_message(
                    chat_id=user_chat_id,
                    from_chat_id=source_chat_id,
                    message_id=i
                )
            except RetryAfter as e:
                logger.warning(f"Rate limit hit. Waiting for {e.retry_after} seconds.")
                await asyncio.sleep(e.retry_after)
            except Exception as e:
                logger.error(f"Error forwarding message ID {i}: {e}")
                continue 

    except Exception as e:
        logger.error(f"Error forwarding message thread: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"An error occurred: {str(e)}")
    finally:
        await client.disconnect()    

async def forwrand_command(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id

    now = datetime.now()

    if chat_id not in chat_cooldowns:
        chat_cooldowns[chat_id] = {'count': 0, 'cooldown_expiry': now + COOLDOWN_DURATION}

    chat_info = chat_cooldowns[chat_id]
    count = chat_info['count']
    cooldown_expiry = chat_info['cooldown_expiry']

    # Check if the chat is currently throttled
    if now < cooldown_expiry and count >= MAX_USES_BEFORE_COOLDOWN:
        return

    await client.start()

    try:
        # Get the last message in the chat
        last_message = await client.get_messages(chat_id, limit=1)

        if not last_message:
            await update.message.reply_text("No messages found in this chat.")
            return

        last_message_id = last_message[0].id

        success = False
        attempt = 0
        MAX_FORWRAND_RETRIES = 5

        while not success:
            random_message_id = random.randint(2, last_message_id)
            attempt += 1

            try:
                forwarded_message = await context.bot.forward_message(
                    chat_id=update.message.chat_id,
                    from_chat_id=chat_id,
                    message_id=random_message_id
                )
                success = True

                redis_key = f"{chat_id}_{forwarded_message.message_id}"
                redis_client.set(redis_key, random_message_id, ex=REDIS_TTL)

            except Exception as e:
                if attempt >= MAX_FORWRAND_RETRIES:
                    raise

        chat_cooldowns[chat_id]['count'] += 1

        if datetime.now() > cooldown_expiry and chat_cooldowns[chat_id]['count'] >= MAX_USES_BEFORE_COOLDOWN:
            chat_cooldowns[chat_id]['cooldown_expiry'] = now + COOLDOWN_DURATION
            chat_cooldowns[chat_id]['count'] = 1

    except Exception as e:
        logger.error(f"Error processing forwrand_command: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"An error occurred: {str(e)}")
    finally:
        await client.disconnect()

async def forward_id_command(update: Update, context: CallbackContext) -> None:
    if not update.message.reply_to_message:
        await update.message.reply_text('You need to reply to a message.')
        return

    reply_to_message_id = update.message.reply_to_message.message_id

    redis_key = f"{update.message.chat_id}_{reply_to_message_id}"
    original_message_id = redis_client.get(redis_key)
    if original_message_id:
        await update.message.reply_text(original_message_id)
    else:
        await update.message.reply_text('No message id in cache')

    return

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Hi! Please add me to the chat or channel to be able to forward messages from it.')

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = r"""
🤖 *Bot Commands Guide* 📜

Welcome to your message forwarding assistant\! Below are the commands you can use:

/forward \[<source\_chat\>\] <message\_id\>
\- _Forward a specific message from a chat\._
\- Usage: Forward a single message by its ID\. The chat name is optional if you’re already in the chat\.
\- Example: `/forward 123456` or `/forward channelname 123456`

/forward\_reply
\- _Forward the original message in a reply chain\._
\- Usage: Reply to a message and use this command to forward the original message\.
\- Example: Reply with `/forward\_reply` to forward the original message in the thread\.

/forward\_thread \[\[<source\_chat\>\] <message\_id\>\]
\- _Forward a thread of replies or a specific message\._
\- Usage: Forward an entire thread starting from a message ID or the message you replied to\. Messages will be sent to your private chat\. You need to start the bot for yourself\.
\- Example: `/forward\_thread 123456` or reply with `/forward\_thread`

/forward\_n \[<source\_chat\>\] <message\_id\> <count\>
\- _Forward a sequence of messages\._
\- Usage: Forward a series of `n` messages starting from the specified message ID\. Messages will be sent to your private chat\. You need to start the bot for yourself\. Max count is 100 to avoid rate limiting\.
\- Example: `/forward\_n 123456 10` or `/forward\_n channelname 123456 10`

/forwrand
\- _Forward a random message from the chat\._
\- Usage: Just send command in the chat and the bot will reply with random message from the chat\. Rate limited, 2 forwrands/15s\.

/forward\_id
\- _Send original id of forwarded message\._
\- Usage: Send in reply to forwarded message\.

Commands like `/forward\_id`, `/forward\_reply`, `/forward\_thread`, `/forward\_n` will work on messages forwarded by `/forward`, `/forward\_reply`, `/forwrand` only for five minutes\.

If you need further assistance, feel free to reach out \@lazerate\. Happy forwarding\! 🎉
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)

def main():
    application = Application.builder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("forward", forward_command))
    application.add_handler(CommandHandler("forward_reply", forward_reply_command))
    application.add_handler(CommandHandler("forward_thread", forward_thread_command))
    application.add_handler(CommandHandler("forward_n", forward_n_command))
    application.add_handler(CommandHandler("forwrand", forwrand_command))
    application.add_handler(CommandHandler("forward_id", forward_id_command))

    application.run_polling()

if __name__ == '__main__':
    main()