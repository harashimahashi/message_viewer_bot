from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from telegram.error import RetryAfter
from telegram.constants import ParseMode
from telethon import TelegramClient
from dotenv import load_dotenv
import logging
import traceback
import asyncio
import os

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

bot_token = os.getenv("BOT_TOKEN")
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")

client = TelegramClient('bot_session', api_id, api_hash)

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

        await context.bot.forward_message(
            chat_id=update.message.chat_id,
            from_chat_id=source_chat,
            message_id=message_id
        )

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

    await client.start()

    try:
        # Fetch the message the replied-to message is replying to
        message = await client.get_messages(update.message.chat_id, ids=reply_to_message_id)

        logger.error(message);

        if message.reply_to:
            original_message_id = message.reply_to.reply_to_msg_id
            source_chat_id = message.chat_id

            await context.bot.forward_message(
                chat_id=update.message.chat_id,
                from_chat_id=source_chat_id,
                message_id=original_message_id
            )

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
\- Usage: Forward an entire thread starting from a message ID or the message you replied to\. Messages will be sent to your private chat\.
\- Example: `/forward\_thread 123456` or reply with `/forward\_thread`

/forward\_n \[<source\_chat\>\] <message\_id\> <count\>
\- _Forward a sequence of messages\._
\- Usage: Forward a series of `n` messages starting from the specified message ID\. Messages will be sent to your private chat\. Max count is 100 to avoid rate limiting\.
\- Example: `/forward\_n 123456 10` or `/forward\_n channelname 123456 10`

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

    application.run_polling()

if __name__ == '__main__':
    main()