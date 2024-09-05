# Telegram Message Forwarding Bot - message_viewer_bot

This bot is designed to help users retrieve and forward messages from Telegram chats, even those past the 1 million messages limit imposed by Telegram. It offers several commands to forward specific messages, reply chains, threads, or a sequence of messages directly to your private chat.

## Features

- **Retrieve and forward messages past Telegram's 1 million messages limit.**
- **Support for various message forwarding commands.**
- **Flexible usage with optional chat name specification.**
- **Ability to forward reply chains, message threads, or multiple messages at once.**

## Installation

1. **Clone the repository:**

    ```bash
    git clone https://github.com/harashimahashi/message_viewer_bot.git
    cd message_viewer_bot

2. **Set up your environment variables:**


    Create a .env file in the root directory of the project and add your environment variables:

    ```env
    BOT_TOKEN=your-bot-token
    API_ID=your-api-id
    API_HASH=your-api-hash

3. **Install dependencies:**

    Install the necessary Python packages:

    `bash
    pip install -r requirements.txt`

4. **Run the bot:**

    `bash
    python main.py`

## Usage

### Commands

#### `/forward [<source_chat>] <message_id>`
Forward a specific message from a chat.
- **Usage:** Forward a single message by its ID. The chat name is optional if you’re already in the chat.
- **Example:** `/forward 123456` or `/forward channelname 123456`

#### `/forward_reply`
Forward the original message in a reply chain.
- **Usage:** Reply to a message and use this command to forward the original message.
- **Example:** Reply with `/forward_reply` to forward the original message in the thread.

#### `/forward_thread [[<source_chat>] <message_id>]`
Forward a thread of replies or a specific message.
- **Usage:** Forward an entire thread starting from a message ID or the message you replied to. Messages will be sent to your private chat.
- **Example:** `/forward_thread 123456` or reply with `/forward_thread`

#### `/forward_n [<source_chat>] <message_id> <count>`
Forward a sequence of messages.
- **Usage:** Forward a series of `n` messages starting from the specified message ID. Messages will be sent to your private chat. Max count is 100 to avoid rate limiting.
- **Example:** `/forward_n 123456 10` or `/forward_n channelname 123456 10`

#### `/forwrand`
Forwards random message from chat.
- **Usage:** Just send command in the chat and the bot will reply with random message from the chat. Rate limited, 2 forwrands/15s

## License
This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing
Contributions are welcome! Please fork the repository and create a pull request with your changes.