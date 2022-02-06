import logging
import time
import typing

from telegram import Update
from telegram.ext import Updater
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler

import wolt_checker
from data_types import ChatState, ChatInfo

with open("access_token") as access_token_file:
    ACCESS_TOKEN = access_token_file.read()
DEFAULT_INTERVAL_SECONDS = 60

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
state: typing.Dict[int, ChatInfo] = {}


def start_handler(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    context.bot.send_message(
        chat_id=chat_id,
        text="I'm a bot to update you about Wolt venue statuses!\n"
             "If at any point you'd like to restart please send /start",
    )
    context.bot.send_message(
        chat_id=chat_id,
        text="What is the name of the venue you are looking for?",
    )
    state[chat_id] = ChatInfo(state=ChatState.START)


def venue_selection_handler(chat_id: int, context: CallbackContext, update: Update) -> None:
    venues = wolt_checker.get_venue_options(update.message.text)
    prompt = wolt_checker.built_prompt(venues=venues)
    state[chat_id] = ChatInfo(state=ChatState.VENUE_SELECTION, venues=venues)
    context.bot.send_message(chat_id=chat_id, text=prompt)


def is_online_handler(chat_id: int, context: CallbackContext, update: Update) -> None:
    selection = int(update.message.text)
    venue = state[chat_id].venues[selection - 1]
    state[chat_id].venues = None
    is_venue_online = wolt_checker.is_venue_online(venue=venue)
    if is_venue_online:
        context.bot.send_message(chat_id=chat_id, text="Venue is already online!")
        del state[chat_id]
    else:
        context.bot.send_message(
            chat_id=chat_id,
            text="The venues seems to be offline, I'll update you once it is open",
        )
        while not is_venue_online:
            logger.info("Venue is offline, waiting a minute before checking again...")
            time.sleep(DEFAULT_INTERVAL_SECONDS)
            is_venue_online = wolt_checker.is_venue_online(venue=venue)
        context.bot.send_message(chat_id=chat_id, text="The venue is now online!")
        del state[chat_id]


STATE_TO_HANDLER = {
    ChatState.START: venue_selection_handler,
    ChatState.VENUE_SELECTION: is_online_handler,
}


def default_message_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    chat_info = state[chat_id]
    handler = STATE_TO_HANDLER[chat_info.state]
    handler(chat_id=chat_id, context=context, update=update)


def main():
    updater = Updater(token=ACCESS_TOKEN, use_context=True)

    # Start handler
    updater.dispatcher.add_handler(handler=CommandHandler(command='start', callback=start_handler))

    # Default handler
    default_handler = MessageHandler(filters=Filters.text & (~Filters.command), callback=default_message_handler)
    updater.dispatcher.add_handler(handler=default_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
