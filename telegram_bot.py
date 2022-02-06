import logging
import time
import typing

from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

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
    logger.info("Got start request from chat id: %s", chat_id)
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


def search_query_handler(chat_id: int, context: CallbackContext, update: Update) -> None:
    query = update.message.text
    logger.info("Got query from chat id: %s query: %s", chat_id, query)
    venues = wolt_checker.get_venue_options(query)
    if venues:
        prompt = wolt_checker.built_prompt(venues=venues, page_num=0)
        state[chat_id] = ChatInfo(state=ChatState.VENUE_SELECTION, venues=venues)
        context.bot.send_message(chat_id=chat_id, text=prompt)
    else:
        context.bot.send_message(chat_id=chat_id, text="Sorry, there's no venue matching your search\n"
                                                       "If you'd like to try again please reply /start")
        del state[chat_id]


def _select_venue(chat_id: int, context: CallbackContext, update: Update) -> None:
    chat_info = state[chat_id]
    logger.info("Got venue selection from chat id: %s", chat_id)
    selection = int(update.message.text)
    venue = chat_info.venues[selection - 1]
    chat_info.venues = None
    is_venue_online = wolt_checker.is_venue_online(venue=venue)
    if is_venue_online:
        context.bot.send_message(chat_id=chat_id, text="Venue is already online!\n"
                                                       "To search for another venue please reply \"/start\"")
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
        context.bot.send_message(chat_id=chat_id, text="The venue is now online!\n"
                                                       "To search for another venue please reply \"/start\"")
        del state[chat_id]


def _get_next_page(chat_id, context):
    chat_info = state[chat_id]
    logger.info("Got next page from chat id: %s", chat_id)
    chat_info.page_num += 1
    prompt = wolt_checker.built_prompt(venues=chat_info.venues, page_num=chat_info.page_num)
    context.bot.send_message(chat_id=chat_id, text=prompt)


def venue_selection_handler(chat_id: int, context: CallbackContext, update: Update) -> None:
    message_text = update.message.text
    if str.isdigit(message_text):
        _select_venue(chat_id, context, update)
    else:
        _get_next_page(chat_id, context)


STATE_TO_HANDLER = {
    ChatState.START: search_query_handler,
    ChatState.VENUE_SELECTION: venue_selection_handler,
}


def default_message_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if chat_id in state:
        chat_info = state[chat_id]
        handler = STATE_TO_HANDLER[chat_info.state]
        handler(chat_id=chat_id, context=context, update=update)
    else:
        start_handler(update=update, context=context)


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
