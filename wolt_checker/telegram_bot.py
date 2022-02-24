import json
import logging
from dataclasses import asdict

import firebase_admin
from firebase_admin import db
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

import wolt_checker
from data_types import ChatState, ChatInfo

with open("config.json") as config_file:
    config = json.load(config_file)
    ACCESS_TOKEN = config["access_token"]
    ALLOWED_CHATS = config["allowed_chats"]
    DATABASE_URL = config["database_url"]
DEFAULT_INTERVAL_SECONDS = 60

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
cred = firebase_admin.credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})
state_ref = db.reference("/state")


def _is_chat_allowed(chat_id: int) -> bool:
    return chat_id in ALLOWED_CHATS


def _handle_not_allowed_chat(chat_id: int, context: CallbackContext):
    logger.info("Got unauthorized start request from chat id: %s", chat_id)
    context.bot.send_message(
        chat_id=chat_id,
        text="I'm sorry but you are currently an unrecognized user. To gain access to the bot please ask the owner"
             f"to add you to the allowed users. Your chat id {chat_id}",
    )


def start_handler(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    if _is_chat_allowed(chat_id):
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
        state_ref.child(str(chat_id)).set(asdict(ChatInfo(state=ChatState.START.value)))
    else:
        _handle_not_allowed_chat(chat_id, context)


def search_query_handler(chat_id: int, context: CallbackContext, update: Update) -> None:
    query = update.message.text
    logger.info("Got query from chat id: %s query: %s", chat_id, query)
    venues = wolt_checker.get_venue_options(query)
    if venues:
        prompt = wolt_checker.built_prompt(venues=venues, page_num=0)
        state_ref.child(str(chat_id)).set(asdict(ChatInfo(state=ChatState.VENUE_SELECTION.value, venues=venues)))
        context.bot.send_message(chat_id=chat_id, text=prompt)
    else:
        context.bot.send_message(chat_id=chat_id, text="Sorry, there's no venue matching your search\n"
                                                       "If you'd like to try again please reply /start")
        state_ref.child(str(chat_id)).set({})


def _select_venue(chat_id: int, context: CallbackContext, update: Update) -> None:
    chat_info = ChatInfo(**state_ref.child(str(chat_id)).get())
    logger.info("Got venue selection from chat id: %s", chat_id)
    selection = int(update.message.text)
    venue = chat_info.venues[selection - 1]
    chat_info.venues = None
    is_venue_online = wolt_checker.is_venue_online(venue=venue)
    if is_venue_online:
        context.bot.send_message(chat_id=chat_id, text="The venue is already online!\n"
                                                       "To search for another venue please reply /start")
        state_ref.child(str(chat_id)).set({})
    else:
        context.bot.send_message(
            chat_id=chat_id,
            text="The venues seems to be offline, I'll update you once it is open",
        )
        context.job_queue.run_repeating(callback=_poll_venue, interval=DEFAULT_INTERVAL_SECONDS, context={
            "chat_id": chat_id,
            "venue": venue,
        })


def _poll_venue(context: CallbackContext) -> None:
    chat_id = context.job.context["chat_id"]
    venue = context.job.context["venue"]
    is_venue_online = wolt_checker.is_venue_online(venue=venue)
    logger.info("Polling for chat id: %s", chat_id)
    if is_venue_online:
        context.bot.send_message(chat_id=chat_id, text="The venue is now online!\n"
                                                       "To search for another venue please reply /start")
        state_ref.child(str(chat_id)).set({})
        context.job.schedule_removal()


def _get_next_page(chat_id: int, context: CallbackContext) -> None:
    chat_info = ChatInfo(**state_ref.child(str(chat_id)).get())
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
    ChatState.START.value: search_query_handler,
    ChatState.VENUE_SELECTION.value: venue_selection_handler,
}


def default_message_handler(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    chat_info_dict = state_ref.child(str(chat_id)).get()
    if chat_info_dict is not None:
        chat_info = ChatInfo(**chat_info_dict)
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
