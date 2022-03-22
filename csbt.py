# https://core.telegram.org/bots/api
import random
import re

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import common
import logging

global bot

bot_token, bot_username = common.build_tuple('tk.pv')

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
commands = common.build_tuple_of_tuples('hp.pv')


def command_help(update: Update, context: CallbackContext):
    weight_large = 3
    weight_small = 1
    command_help_str = ''
    for help_item in commands:
        command, desc = help_item
        command_help_str += '/%s\t%s\n' % (command, desc)
    confirmation = common.build_tuple('cf.pv')

    # Weights of confirmation messages
    weights = []
    for i in range(len(confirmation) - 1):
        # Weights of 3 for normal messages
        weights.append(weight_large)
    # Weights 1 for the special message
    weights.append(weight_small)

    # Append the confirmation message
    command_help_str += '\n' + random.choices(population=confirmation, weights=weights)[0]
    for i in range(random.randint(0, 2)):
        command_help_str += 'ㅎ'
    update.message.reply_text(str.strip(command_help_str))


def alarm(context: CallbackContext) -> None:
    job = context.job
    context.bot.send_message(job.context, text=common.format_quiet_chat('설정된 타이머 시간에 도달했습니다.'))


def remove_job_if_exists(chat_id: str, context: CallbackContext) -> bool:
    # Remove job with given name. Returns whether job was removed.
    current_jobs = context.job_queue.get_jobs_by_name(chat_id)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


# TODO: Listen to specified keywords instead of commands.
def msg_listener(update: Update, context: CallbackContext) -> None:
    try:
        # msg = int(context.args[0])
        msg = update.message.text
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /set <seconds>')


def set_timer(update: Update, context: CallbackContext, minutes: int) -> None:
    # Add a job to the queue.
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    context.job_queue.run_once(alarm, minutes * 60, context=chat_id, name=str(chat_id))
    # TODO: '~분 남았습니다.' 알림
    # https://stackoverflow.com/questions/52556939, https://stackoverflow.com/questions/47167193

    update.message.reply_text(common.format_quiet_chat('%d분 타이머가 설정되었습니다.') % minutes)
    if job_removed:
        update.message.reply_text(common.format_quiet_chat('기존에 설정된 타이머는 취소합니다.') % minutes)


def cancel_timer(update: Update, context: CallbackContext) -> None:
    # Remove the scheduled job if the user changed their mind.
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = '타이머가 취소되었습니다.' if job_removed else '활성화된 타이머가 없습니다.'
    update.message.reply_text(common.format_quiet_chat(text))


def error(update: Updater, context: CallbackContext):
    # Log Errors caused by Updates
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def order_1(update: Update, context: CallbackContext):
    directions = random.choice(common.build_tuple_of_tuples('01-0.pv'))
    for direction in directions:
        update.message.reply_text(direction)
    common_directions = common.build_tuple('01-1.pv')
    for common_direction in common_directions:
        update.message.reply_text(common_direction)


def order_2(update: Update, context: CallbackContext):
    word_0 = random.choice(common.build_tuple('02-0.pv'))
    word_1 = random.choice(common.build_tuple('02-1.pv'))
    word_2 = random.choice(common.build_tuple('02-2.pv'))
    order_str = word_0 + word_1 + word_2
    update.message.reply_text(order_str)
    if order_str[0].isdigit():
        minutes = int(re.search(r'\d+', order_str).group())
        set_timer(update, context, minutes)
        print('Timer set for %d' % minutes)


# TODO: Play recorded audios.
def main():
    # Start the bot
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(bot_token, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    dp.add_error_handler(error)
    dp.add_handler(CommandHandler('help', command_help))

    # Add handlers for alarms
    dp.add_handler(CommandHandler('cancel', cancel_timer))
    # Add message handlers
    for number, help_item in enumerate(commands):
        command, desc = help_item
        if number == 0:
            dp.add_handler(CommandHandler(command, order_1))
        if number == 1:
            dp.add_handler(CommandHandler(command, order_2))

    # TODO: Add a handler for unexpected commands

    # Start the Bot
    updater.start_polling()

    # TODO: Make it private (https://stackoverflow.com/questions/46015319, https://stackoverflow.com/questions/49078320)

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
