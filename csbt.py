# https://core.telegram.org/bots/api
import schedule
from threading import Thread
import random
import re
import telegram
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
import common
import logging


class Constants:
    BOT_TOKEN, BOT_USERNAME = common.build_tuple('token.pv')


# When a direction was sent, is_waiting_* = True.
# When an answer was received, is_waiting_* = False.
is_waiting_answer_yes: bool = False
is_waiting_answer_start: bool = False

# Whether to allow rubbing or not: refreshed daily.
is_allowed: bool = True
denial_count: int = 0

# Duration of rubbing
minutes: int = 2

# Enable logging.
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def command_help(update: Update, context: CallbackContext):
    commands = common.build_tuple_of_tuples('help.pv')
    command_help_str = ''
    for help_item in commands:
        command, desc = help_item
        command_help_str += '/{}\t{}\n'.format(command, desc)

    # Reply to the command.
    update.message.reply_text(str.strip(command_help_str))

    # Send a confirmation message occasionally.
    confirmation = random.choice(common.build_tuple('help_additional.pv'))

    # Append the confirmation message.
    if common.get_random_bool(0.1):
        common.sleep_random_duration(2, 4)
        context.bot.send_message(chat_id=update.message.chat_id, text=add_k(confirmation))


def schedule_checker():
    while True:
        # Check pending jobs.
        schedule.run_pending()
        common.sleep_random_duration(3000, 4200)


def renew_allowing_rubbing():
    global is_allowed
    global denial_count
    is_allowed = common.get_random_bool(0.87)
    print('is_allowed: {}'.format(str(is_allowed)))
    denial_count = 0


def add_k(msg: str) -> str:
    for i in range(random.randint(3, 4)):
        msg += 'ㅋ'
    return msg


def halt(context: CallbackContext) -> None:
    job = context.job
    # TODO: Combine with send_bot_message()
    context.bot.send_message(job.context, text='`(설정된 타이머 시간에 도달했습니다.)`', parse_mode=telegram.ParseMode.MARKDOWN_V2)


def remove_job_if_exists(chat_id: str, context: CallbackContext) -> bool:
    # Remove job with given name. Returns whether job was removed.
    current_jobs = context.job_queue.get_jobs_by_name(chat_id)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def message_listener(update: Update, context: CallbackContext) -> None:
    global is_waiting_answer_yes
    global is_waiting_answer_start
    global minutes

    try:
        msg = update.message.text
        if ((re.search("자위.*(하고.*싶.+|해도.+)[?ㅜㅠ]$", msg) or
             re.search("^(클리|보지).*\s((만지|비비|쑤시)|(만져|비벼|쑤셔|).*요[?ㅜㅠ]$)", msg)) and
                not re.search("(몇\s?분|얼마)", msg)):
            give_rubbing_posture(update, context)
        elif re.search("(몇\s?분|얼마).*요[?ㅜㅠ]$", msg) and re.search("(자위|클리|보지)", msg):
            give_rubbing_duration(update, context)

            is_waiting_answer_yes = True
            is_waiting_answer_start = True
        elif re.search("\d.?분.{0,6}(보지|클리|자위).*[도면].*요[?ㅜㅠ]$", msg):
            # To set an arbitrary timer
            minutes = int(re.search(r'\d+', msg).group())
            set_timer(update, context)
        else:
            # Listen to the answers.
            if is_waiting_answer_yes and re.search("^([네예])", msg):
                print('(대답?: {} / "시작"?: {}) "{}"'
                      .format(str(not is_waiting_answer_yes), str(not is_waiting_answer_start), msg))
                is_waiting_answer_yes = False
                if not is_waiting_answer_start:
                    respond_to_answer(update, context)
            if is_waiting_answer_start and re.search("시작", msg):
                print('(대답?: {} / "시작"?: {}) "{}"'
                      .format(str(not is_waiting_answer_yes), str(not is_waiting_answer_start), msg))
                is_waiting_answer_start = False
                if not is_waiting_answer_yes:
                    respond_to_answer(update, context)

    except (IndexError, ValueError):
        name = common.read_from_file('name.pv')
        update.message.reply_text('메시지를 처리할 수 없습니다. {}에게 보고하고 문제가 해결될 때까지 기다리세요.'.format(name))


def respond_to_answer(update: Update, context: CallbackContext):
    is_k_added = False
    chat_id = update.message.chat_id
    remove_job_if_exists(str(chat_id), context)

    # Give a compliment occasionally.
    if common.get_random_bool(0.1):
        common.sleep_random_duration(2.4, 4.8)
        is_k_added = True
        compliment_phrase = random.choice(common.build_tuple_of_tuples('compliment.pv'))
        for line in compliment_phrase:
            common.sleep_random_duration(1.2, 2.4)
            context.bot.send_message(chat_id=chat_id, text=add_k(line))

    # Give the start direction.
    oo = 'ㅇㅇ '
    word = '시작'
    postfix = '해'
    q_line = ''
    if common.get_random_bool():
        q_line += oo
    q_line += word
    if common.get_random_bool():
        q_line += postfix
    if is_k_added:
        q_line = add_k(q_line)
    common.sleep_random_duration(0.4, 1.2)
    context.bot.send_message(chat_id=chat_id, text=q_line)

    set_timer(update, context)


def give_rubbing_posture(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if is_allowed:
        is_naked = False
        if common.get_random_bool(0.3):
            common.sleep_random_duration(max_sec=0.8)
            nudity_direction = random.choice(common.build_tuple('01-0.pv'))
            context.bot.send_message(chat_id=chat_id, text=nudity_direction)
            is_naked = True

        random_direction = random.choice(common.build_tuple_of_tuples('01-1.pv'))

        # Add a pause before give a direction.
        common.sleep_random_duration(2.4, 3.6)
        for i, line in enumerate(random_direction):
            if is_naked and i == 0:
                line = '그리고 다 벗었으면 ' + line
            common.sleep_random_duration(max_sec=1.2)
            context.bot.send_message(chat_id=chat_id, text=line)
        common.sleep_random_duration(1.6, 2.4)

        # Give common directions.
        give_common_directions(context, update)

    else:
        global denial_count
        last_count = denial_count
        denial_count += 1
        print('New denial count: {:d}'.format(denial_count))

        if last_count == 0:
            common.sleep_random_duration(0.4, 1.2)
            context.bot.send_message(chat_id=chat_id, text='안돼')

            additional_direction = random.choice(common.build_tuple_of_tuples('dont_0.pv'))
            for line in additional_direction:
                common.sleep_random_duration(0.8, 1.6)
                context.bot.send_message(chat_id=chat_id, text=line)
        elif last_count == 1:
            additional_direction = random.choice(common.build_tuple_of_tuples('dont_1.pv'))
            for line in additional_direction:
                common.sleep_random_duration(0.8, 1.6)
                context.bot.send_message(chat_id=chat_id, text=line)
        else:
            send_bot_message(update, context, '데이터 수신을 차단합니다.', True)
            shutdown()


def demand_answer(context: CallbackContext) -> None:
    demanding_line = random.choice(common.build_tuple('demanding_answer.pv'))
    job = context.job
    # TODO: Combine with send_bot_message()
    context.bot.send_message(job.context, text=demanding_line)


def give_common_directions(context, update):
    common_direction_optional = random.choice(common.build_tuple('01-2.pv'))
    # Give an order sometimes.
    if common.get_random_bool(0.3):
        common.sleep_random_duration(max_sec=1.2)
        context.bot.send_message(chat_id=update.message.chat_id, text=common_direction_optional)
    # Always give the orders.
    common_directions_required = common.build_tuple('01-3.pv')
    for line in common_directions_required:
        common.sleep_random_duration(max_sec=1.2)
        context.bot.send_message(chat_id=update.message.chat_id, text=line)


def give_rubbing_duration(update: Update, context: CallbackContext):
    global minutes
    chat_id = update.message.chat_id

    duration_str = random.choice(common.build_tuple('02-0.pv'))
    part_str = random.choice(common.build_tuple('02-1.pv'))
    report_items_str = random.choice(common.build_tuple('02-2.pv'))
    direction_str = duration_str + ' ' + part_str + ' ' + report_items_str
    context.bot.send_message(chat_id=update.message.chat_id, text=direction_str)
    if direction_str[0].isdigit():
        minutes = int(re.search(r'\d+', direction_str).group())
    else:
        minutes = 2

    remove_job_if_exists(str(chat_id), context)
    context.job_queue.run_once(demand_answer, 16, context=chat_id, name=str(chat_id))
    print('Waiting answering for 16"')


def set_timer(update: Update, context: CallbackContext) -> None:
    # Add a job to the queue.
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)

    seconds = minutes * 60
    context.job_queue.run_once(halt, seconds, context=chat_id, name=str(chat_id))
    print('Timer set for {}\''.format(minutes))

    # TODO: '~분 남았습니다.' 알림
    # https://stackoverflow.com/questions/52556939, https://stackoverflow.com/questions/47167193

    common.sleep_random_duration(0.8, 1.2)
    send_bot_message(update, context, '{:d}분 타이머가 설정되었습니다.'.format(minutes), True)
    if job_removed:
        send_bot_message(update, context, '기존 설정 타이머는 취소합니다.', True)


def send_bot_message(update: Update, context: CallbackContext, msg: str, is_reply: bool = False):
    if is_reply:
        update.message.reply_text(text='`({})`'.format(msg), parse_mode=telegram.ParseMode.MARKDOWN_V2)
    else:
        context.bot.send_message(chat_id=update.message.chat_id,
                                 text='`({})`'.format(msg), parse_mode=telegram.ParseMode.MARKDOWN_V2)


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


def shutdown():
    print('Called shutdown command.')
    common.sleep_random_duration(3600 * 8, 3600 * 9)


# TODO: Play recorded audios.
def main():
    # Create the job in schedule.(https://stackoverflow.com/a/60867438/17198283)
    schedule.every().day.at("09:00").do(renew_allowing_rubbing)
    renew_allowing_thread = Thread(target=schedule_checker)
    renew_allowing_thread.daemon = True  # https://stackoverflow.com/a/11816038/17198283
    renew_allowing_thread.start()

    # Get the dispatcher to register handlers
    updater = Updater(Constants.BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_error_handler(error)

    # Note: Disable privacy mode by /setprivacy to recognize "normal" messages.
    # (https://stackoverflow.com/a/67163946/17198283)
    dp.add_handler(MessageHandler(Filters.text & (~ Filters.command), message_listener))
    dp.add_handler(CommandHandler('help', command_help))

    # Add handlers to cancel alarms
    dp.add_handler(CommandHandler('cancel', cancel_timer))
    # Add message handlers
    commands = common.build_tuple_of_tuples('help.pv')
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
