# https://core.telegram.org/bots/api
import random
import re
import telegram
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
import common
import logging


class Constants:
    BOT_TOKEN, BOT_USERNAME = common.build_tuple('token.pv')


# Enable logging.
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
commands = common.build_tuple_of_tuples('help.pv')


def command_help(update: Update, context: CallbackContext):
    command_help_str = ''
    for help_item in commands:
        command, desc = help_item
        command_help_str += '/{}\t{}\n'.format(command, desc)

    # Reply to the command.
    update.message.reply_text(str.strip(command_help_str))

    # Send a confirmation message occasionally.
    confirmation = random.choice(common.build_tuple('confirmation.pv'))

    # Append the confirmation message.
    if random.uniform(0, 1) < 0.1:
        common.pause_briefly(2, 4)
        context.bot.send_message(chat_id=update.message.chat_id, text=add_k(confirmation))


def add_k(msg: str) -> str:
    for i in range(random.randint(3, 5)):
        msg += 'ㅋ'
    return msg


def halt(context: CallbackContext) -> None:
    job = context.job
    # TODO: Combine with send_bot_message()
    context.bot.send_message(job.context, text='`설정된 타이머 시간에 도달했습니다.`', parse_mode=telegram.ParseMode.MARKDOWN)


def remove_job_if_exists(chat_id: str, context: CallbackContext) -> bool:
    # Remove job with given name. Returns whether job was removed.
    current_jobs = context.job_queue.get_jobs_by_name(chat_id)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def order(update: Update, context: CallbackContext) -> None:
    try:
        msg = update.message.text
        if re.search("^자위.*(하고.*싶|해도.+\?([ㅜㅠ]){0,3}$)", msg) or\
                re.search("^(클리|보지).*\s((만지|비비|쑤시)|(만져|비벼|쑤셔|).*\?([ㅜㅠ]){0,3}$)", msg):
            give_rubbing_posture(update, context)
        if re.search("^(몇.?분|얼마).*\?([ㅜㅠ]){0,3}$", msg):
            give_rubbing_duration(update, context)
    except (IndexError, ValueError):
        name = common.read_from_file('name.pv')
        update.message.reply_text('메시지를 처리할 수 없습니다. {}에게 보고하고 문제가 해결될 때까지 기다리세요.'.format(name))


def give_rubbing_posture(update: Update, context: CallbackContext):
    is_naked = False
    if random.uniform(0, 1) < 0.3:
        common.pause_briefly(max_pause=0.8)
        nudity_direction = random.choice(common.build_tuple('01-0.pv'))
        context.bot.send_message(chat_id=update.message.chat_id, text=nudity_direction)
        is_naked = True

    random_direction = random.choice(common.build_tuple_of_tuples('01-1.pv'))

    # Add a pause before picking.
    common.pause_briefly(2.4, 3.6)
    for i, line in enumerate(random_direction):
        if is_naked and i == 0:
            line = '그리고 다 벗었으면 ' + line
        common.pause_briefly(max_pause=1.2)
        context.bot.send_message(chat_id=update.message.chat_id, text=line)
    common.pause_briefly(1.6, 2.4)

    # Give common directions.
    common_direction_optional = random.choice(common.build_tuple('01-2.pv'))
    # Give an order sometimes.
    if random.uniform(0, 1) < 0.3:
        common.pause_briefly(max_pause=1.2)
        context.bot.send_message(chat_id=update.message.chat_id, text=common_direction_optional)
    # Always give the orders.
    common_directions_required = common.build_tuple('01-3.pv')
    for line in common_directions_required:
        common.pause_briefly(max_pause=1.2)
        context.bot.send_message(chat_id=update.message.chat_id, text=line)


def give_rubbing_duration(update: Update, context: CallbackContext):
    word_0 = random.choice(common.build_tuple('02-0.pv'))
    word_1 = random.choice(common.build_tuple('02-1.pv'))
    word_2 = random.choice(common.build_tuple('02-2.pv'))
    direction_str = word_0 + ' ' + word_1 + ' ' + word_2

    context.bot.send_message(chat_id=update.message.chat_id, text=direction_str)
    if direction_str[0].isdigit():
        minutes = int(re.search(r'\d+', direction_str).group())
        set_timer(update, context, minutes)
        print('Timer set for {}'.format(minutes))


def set_timer(update: Update, context: CallbackContext, minutes: int) -> None:
    # Add a job to the queue.
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)

    seconds = minutes * 60
    context.job_queue.run_once(halt, seconds, context=chat_id, name=str(chat_id))
    # TODO: '~분 남았습니다.' 알림
    # https://stackoverflow.com/questions/52556939, https://stackoverflow.com/questions/47167193

    common.pause_briefly(0.8, 1.2)
    send_bot_message(update, context, '{:d}분 타이머가 설정되었습니다.'.format(minutes), True)
    if job_removed:
        send_bot_message(update, context, '기존 설정 타이머는 취소합니다.', True)


def send_bot_message(update: Update, context: CallbackContext, msg: str, is_reply: bool = False):
    if is_reply:
        update.message.reply_text(text='`{}`'.format(msg), parse_mode=telegram.ParseMode.MARKDOWN)
    else:
        context.bot.send_message(chat_id=update.message.chat_id, text=msg, parse_mode=telegram.ParseMode.MARKDOWN)


def cancel_timer(update: Update, context: CallbackContext) -> None:
    # Remove the scheduled job if the user changed their mind.
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    msg = '타이머가 취소되었습니다.' if job_removed else '활성화된 타이머가 없습니다.'
    send_bot_message(update, context, msg, True)


def error(update: Updater, context: CallbackContext):
    # Log Errors caused by Updates
    logger.warning('Update {} caused error {}'.format(update, context.error))


def order_1(update: Update, context: CallbackContext):
    give_rubbing_posture(update, context)


def order_2(update: Update, context: CallbackContext):
    give_rubbing_duration(update, context)


# TODO: Play recorded audios.
def main():
    # Start the bot
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(Constants.BOT_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    dp.add_error_handler(error)

    # Note: Disable privacy mode by /setprivacy to recognize "normal" messages.
    # (https://stackoverflow.com/a/67163946/17198283)
    dp.add_handler(MessageHandler(Filters.text & (~ Filters.command), order))
    dp.add_handler(CommandHandler('help', command_help))

    # Add handlers to cancel alarms
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
