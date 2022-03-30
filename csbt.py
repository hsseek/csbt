# https://python-telegram-bot.readthedocs.io/en/stable/
import time
import datetime

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
    BOT_TOKEN = common.read_from_file('token.pv')

    PROBABILITY_ALLOWED = 1.1  # Decrease below 1 later.(1 => 100% allowed)
    SEC_WAITING_RESPONSE = 20
    SEC_WAITING_SHUTDOWN = 90
    SEC_SESSION_COOLDOWN = 3600

    JOB_TIMER = 'timer'
    JOB_LITTLE_LEFT = 'little_left'
    JOB_UNBLOCK = 'UNBLOCK'
    LITTLE_TIME_MIN = 1
    JOB_ACTIVATE = 'activate'
    JOB_INFORM_CYCLE_STATUS = 'inform_cycle_status'
    JOB_DECLARE_START = 'declare_start'
    JOB_ASK_SF = 'ask_sf'

    JOB_DEMAND_RESPONSE = 'demand_response'
    JOB_WAIT_SHUTDOWN = 'wait_shutdown'


# Dispatcher and handlers
dispatcher: Updater.dispatcher

is_waiting_response_yes: bool = False
is_waiting_response_start: bool = False

# Whether to allow rubbing or not: refreshed daily.
is_allowed: bool = True
denial_count: int = 0

# Specifying behavior of rubbing
is_direction_given = False
is_to_suppress = True

# Activity sf handlers
is_s_listening = False
is_f_listening = False
is_suppression_successful = False

# Activity of a session
is_active = True
reactivated_time: datetime = datetime.datetime.now()

rubbing_min: int = 0
pause_min: int = 0
repeat: int = 0
cycle_number: int = 0

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
    update.effective_message.reply_text(str.strip(command_help_str))

    # Send a confirmation message occasionally.
    confirmation = random.choice(common.build_tuple('help_additional.pv'))

    # Append the confirmation message.
    if common.get_random_bool(0.1):
        common.sleep_random_seconds(2, 4)
        context.bot.send_message(chat_id=update.effective_message.chat_id, text=confirmation)


def schedule_checker():
    while True:
        # Check pending jobs.
        schedule.run_pending()
        common.sleep_random_seconds(3000, 4200)


def renew_allowing_rubbing():
    global is_allowed
    global denial_count
    is_allowed = common.get_random_bool(Constants.PROBABILITY_ALLOWED)
    print('is_allowed: {}'.format(str(is_allowed)))
    denial_count = 0


def go_off(context: CallbackContext) -> None:
    chat_id = context.job.context
    send_informative_message(chat_id, context, '설정된 타이머 시간에 도달했습니다.')


def has_little_left(context: CallbackContext) -> None:
    chat_id = context.job.context
    send_informative_message(chat_id, context, '{:d}분 남았습니다.'.format(Constants.LITTLE_TIME_MIN))


def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
    # Remove job with given name. Returns whether job was removed.
    # https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/timerbot.py
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
        print("{} job removed.".format(name))
    return True


def unlock_ordering() -> None:
    global is_direction_given
    if is_direction_given:
        is_direction_given = False
        print("Direction unlocked: new direction can be given.")
    else:
        print("Direction already unlocked. Don't change the state.")


def lock_giving_direction() -> None:
    global is_direction_given
    if not is_direction_given:
        is_direction_given = True
        print("Direction locked: new direction won't be given.")
    else:
        print("Direction already locked. Don't change the state.")


def interpret_message(update: Update, context: CallbackContext) -> None:
    global is_waiting_response_yes
    global is_waiting_response_start
    global is_direction_given

    message = update.effective_message
    message_content = message.text
    chat_id = message.chat_id
    try:
        if re.search("(몇\s?분|얼마).*요.?[?ㅜㅠ]$", message_content) and re.search("(보지|클리|자위)", message_content):
            # A message about duration. Equivalent to /2.
            give_2(update, context)
        elif re.search("\d.?분.{0,6}(보지|클리|자위).*[할도면].*요.?[?ㅜㅠ]$", message_content):
            # A message about simple directions
            duration_min = int(re.search(r'\d+', message_content).group())
            send_go(context, chat_id)
            set_termination_timer(message, context, duration_min)
        elif ((re.search("자위.*(하고.*싶.+|해도.+)[?ㅜㅠ]$", message_content) or
               re.search("^(클리|보지).*\s((만지|비비|쑤시)|(만져|비벼|쑤셔|).*요.?[?ㅜㅠ]$)", message_content)) and
              not re.search("(몇\s?분|얼마)", message_content)):
            # A message about posture. Equivalent to /1.
            give_1(update, context)
        else:  # Listen to the answers.
            # [warn_then_block -> demand_response -> is_waiting_response_* = True]
            # But we are not calling warn_then_block.
            # So, is_waiting_response_* = False always.
            # As a result, the following if conditions can never be True, for now.
            if is_waiting_response_yes and re.search("^([네넹예])", message_content):
                is_waiting_response_yes = False
                print('"{}" (대답?: {} / "시작"?: {})'
                      .format(message_content, str(not is_waiting_response_yes), str(not is_waiting_response_start)))
                if not is_waiting_response_start:
                    give_permission_to_start(message, context)
            if is_waiting_response_start and re.search("시작", message_content):
                is_waiting_response_start = False
                print('"{}" (대답?: {} / "시작"?: {})'
                      .format(message_content, str(not is_waiting_response_yes), str(not is_waiting_response_start)))
                if not is_waiting_response_yes:
                    give_permission_to_start(message, context)
    except (IndexError, ValueError):
        contact = common.read_from_file('contact.pv')
        update.effective_message.reply_text('메시지를 처리할 수 없습니다. {}로 문제를 보고하고 문제가 해결될 때까지 기다리세요.'.format(contact))


def send_random_lines(context: CallbackContext, chat_id: int, filename: str):
    phrase = random.choice(common.build_tuple_of_tuples(filename))
    for line in phrase:
        common.sleep_random_seconds(1.6, 2.4)
        context.bot.send_message(chat_id=chat_id, text=line)


def stop_waiting_responses(context: CallbackContext):
    global is_waiting_response_yes
    global is_waiting_response_start

    is_waiting_response_yes = False
    is_waiting_response_start = False
    remove_job_if_exists(Constants.JOB_DEMAND_RESPONSE, context)
    remove_job_if_exists(Constants.JOB_WAIT_SHUTDOWN, context)


def give_permission_to_start(message: telegram.Message, context: CallbackContext, timer_min: int = 0):
    chat_id = message.chat_id

    # Cancel the warning message and the punishment: responded well.
    stop_waiting_responses(context)

    # TODO: Play recorded voice occasionally.
    # Give a compliment occasionally.
    if common.get_random_bool(0.05):
        common.sleep_random_seconds(1.2, 2)
        send_random_lines(context, chat_id, 'compliment.pv')

    common.sleep_random_seconds(1.2, 2)
    send_go(context, chat_id)
    if timer_min:
        set_termination_timer(message, context, timer_min)
    else:
        inactivate(chat_id, context)


def inactivate(chat_id, context: CallbackContext, duration_sec: int = Constants.SEC_SESSION_COOLDOWN):
    global is_active, reactivated_time
    # Update reactivating time.
    reactivated_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_sec)

    unlock_ordering()  # The past directions is no longer valid.
    is_active = False  # Instead, the session is now inactive.
    print('Session inactive for {:d} minutes.'.format(int(duration_sec / 60)))
    context.job_queue.run_once(activate_session, Constants.SEC_SESSION_COOLDOWN,
                               context=chat_id, name=Constants.JOB_ACTIVATE)


def send_go(context, chat_id):
    # bot.send_voice(file_id)
    # https://python-telegram-bot.readthedocs.io/en/stable/telegram.bot.html#telegram.Bot.send_voice
    # https://rdrr.io/cran/telegram.bot/man/sendVoice.html
    # TODO: Play recorded voice occasionally.
    common.sleep_random_seconds()
    # Give the start direction.
    go_line = '시작'
    if common.get_random_bool():
        go_line += '해'
    common.sleep_random_seconds()
    context.bot.send_message(chat_id=chat_id, text=go_line)


def send_incomplete_msg(update: Update, context: CallbackContext):
    msg = '기존 지시 완료가 확인되지 않았습니다.'
    message = update.effective_message
    send_informative_message(message.chat_id, context, msg, message)


def send_inactive_msg(update: Update, context: CallbackContext):
    global reactivated_time

    hour = reactivated_time.strftime("%-H")
    minute = (reactivated_time + datetime.timedelta(minutes=1)).strftime("%-M")

    msg = '비활성화 상태입니다. {}시 {}분에 다시 활성화됩니다.'.format(hour, minute)
    chat_id = update.effective_message.chat_id
    send_informative_message(chat_id, context, msg)


def inform_cycle_status(context: CallbackContext):
    global pause_min, repeat, cycle_number
    chat_id = context.job.context

    cycle_number += 1
    send_informative_message(chat_id, context, '설정된 타이머 시간에 도달했습니다.)\n({:d}분 뒤 다시 타이머가 시작됩니다: {:d}세트 중 {:d}세트 완료'
                             .format(pause_min, repeat, cycle_number))


def declare_start(context: CallbackContext):
    global rubbing_min
    message = context.job.context
    if isinstance(message, telegram.Message):
        chat_id = message.chat_id
        send_go(context, chat_id)
        send_informative_message(chat_id, context, '{}분 타이머가 설정되었습니다.'.format(rubbing_min))


def ask_sf(context: CallbackContext):
    remove_job_if_exists(Constants.JOB_INFORM_CYCLE_STATUS, context)
    remove_job_if_exists(Constants.JOB_DECLARE_START, context)
    remove_job_if_exists(Constants.JOB_TIMER, context)
    remove_job_if_exists(Constants.JOB_LITTLE_LEFT, context)

    global is_to_suppress
    if is_to_suppress:
        global repeat
        chat_id = context.job.context
        send_informative_message(chat_id, context, '설정된 타이머 시간에 도달했습니다.)\n({:d}세트를 모두 완료하였습니다.'
                                 .format(repeat))
        time.sleep(0.8)

    global is_f_listening, is_s_listening
    is_f_listening = True  # Activate all the handlers.
    is_s_listening = True
    commands = common.build_tuple_of_tuples('duration_sf.pv')
    sup_commands_str = ''
    for command in commands:
        command, desc = command
        sup_commands_str += '/{}\t{}\n'.format(command, desc)
    context.bot.send_message(context.job.context, text=sup_commands_str)


def give_1(update: Update, context: CallbackContext, nested: bool = False):
    global is_direction_given
    global is_waiting_response_yes, is_waiting_response_start
    global is_active, reactivated_time
    global is_to_suppress, is_suppression_successful
    message = update.effective_message
    chat_id = message.chat_id
    is_to_suppress = common.get_random_bool(0.8)

    if is_allowed:
        if is_direction_given:
            send_incomplete_msg(update, context)
        elif not is_active:
            send_inactive_msg(update, context)
        else:
            lock_giving_direction()  # Prevent generating another direction.
            is_naked = False
            if common.get_random_bool(0.33) and not is_suppression_successful:
                common.sleep_random_seconds(max_sec=0.8)
                nudity_direction = random.choice(common.build_tuple('01-0.pv'))
                context.bot.send_message(chat_id=chat_id, text=nudity_direction)
                common.sleep_random_seconds(1.6, 2.4)
                is_naked = True

            random_direction = random.choice(common.build_tuple_of_tuples('01-1.pv'))
            for i, line in enumerate(random_direction):
                if is_naked and i == 0:  # Concatenate the first line.
                    line = '그리고 다 벗었으면 ' + line
                common.sleep_random_seconds()
                context.bot.send_message(chat_id=chat_id, text=line)

            # Give an order sometimes.
            if common.get_random_bool(0.7):
                send_random_lines(context, chat_id, '01-2.pv')

            if nested:  # The duration is going to be given.
                # Give time to prepare.
                if is_naked:
                    additional_sec = 10 * random.randint(0, 3)
                    pause_sec = 60 + additional_sec
                    if additional_sec > 0:
                        sec_str = ' {}초'.format(additional_sec)
                    else:
                        sec_str = ''
                    common.sleep_random_seconds(1.6, 2.4)
                    context.bot.send_message(chat_id=chat_id, text='1분{} 줄 테니까 옷 다 벗어'.format(sec_str))
                    common.sleep_random_seconds(1.6, 2.4)
                    context.bot.send_message(chat_id=chat_id, text='준비 끝났으면 가슴 만지면서 자위 준비하고 있어')
                    common.sleep_random_seconds()
                    set_timer(message, context, pause_sec)
                else:
                    common.sleep_random_seconds()
                    context.bot.send_message(chat_id=chat_id, text='자세 준비해')
                    pause_sec = random.randint(12, 24)
                    send_informative_message(chat_id, context, '{}초 뒤 자위 시간 명령을 송신합니다.'.format(pause_sec))
                time.sleep(pause_sec)
            else:
                give_permission_to_start(message, context)

            # (Deprecated) Demand responses. If properly responded, a permission will be given.
            # warn_then_block(update, context)
            # Or, a user can ask for the duration, which will give permission immediately.
    else:
        # Not allowed, but asked the command.
        global denial_count
        last_count = denial_count
        denial_count += 1
        print('New denial count: {:d}'.format(denial_count))

        if last_count == 0:
            common.sleep_random_seconds(0.4, 1.2)
            context.bot.send_message(chat_id=chat_id, text='안돼')

            # TODO: Play recorded voice occasionally.
            send_random_lines(context, chat_id, 'dont-0.pv')
        elif last_count == 1:
            send_random_lines(context, chat_id, 'dont-1.pv')
        else:
            send_informative_message(chat_id, context, '데이터 수신을 차단합니다.')
            blocked_sec = random.randint(3600 * 7, 3600 * 9)
            inactivate(chat_id, context, blocked_sec)


def give_2(update: Update, context: CallbackContext):
    global is_direction_given, is_active
    global is_to_suppress
    message = update.effective_message
    chat_id = message.chat_id

    if is_direction_given:
        send_incomplete_msg(update, context)
    elif not is_active:
        send_inactive_msg(update, context)
    else:
        give_1(update, context, True)
        opening = random.choice(('이번엔', '오늘은', ''))
        if is_to_suppress:  # Suppressing
            global rubbing_min, pause_min, repeat, cycle_number
            cycle_number = 0

            objective_str = random.choice(common.build_tuple('02-0-0.pv'))
            common.sleep_random_seconds()
            context.bot.send_message(chat_id=chat_id, text=opening + ' ' + objective_str)
            common.sleep_random_seconds(1.6, 2.4)  # Suspending

            strings = random.choice(common.build_tuple_of_tuples('02-0-1.pv'))
            integers = []
            for value in strings:
                integers.append(int(value))
            rubbing_min, pause_min, repeat = integers
            duration_str = '{:d}분 동안 보지 털고 {:d}분 쉬기 {:d}세트 하고'.format(rubbing_min, pause_min, repeat)
            context.bot.send_message(chat_id=chat_id, text=duration_str)
            common.sleep_random_seconds()  # Extra pause for the user to read the lines.

            send_random_lines(context, chat_id, '02-0-2.pv')
            global is_f_listening
            is_f_listening = True  # Activate handler to receive a failure report.

            unit_interval = (rubbing_min + pause_min) * 60
            for i in range(repeat):
                firing_time = unit_interval * i
                context.job_queue.run_once(declare_start, firing_time,
                                           context=message, name=Constants.JOB_DECLARE_START)
                if i < repeat - 1:  # Other than the last cycle.
                    context.job_queue.run_once(inform_cycle_status, rubbing_min * 60 + firing_time,
                                               context=chat_id, name=Constants.JOB_INFORM_CYCLE_STATUS)
                    # context (object, optional) – Additional data needed for the callback function.
                    # https://python-telegram-bot.readthedocs.io/en/stable/telegram.ext.jobqueue.html#telegram.ext.JobQueue.run_monthly
            overall_duration = unit_interval * repeat - pause_min * 60 + 3
            context.job_queue.run_once(ask_sf, overall_duration, context=chat_id, name=Constants.JOB_ASK_SF)
        else:  # Rushing
            objective_str = random.choice(common.build_tuple('02-1-0.pv'))
            common.sleep_random_seconds()
            context.bot.send_message(chat_id=chat_id, text=opening + ' ' + objective_str)
            common.sleep_random_seconds(1.6, 2.4)  # Suspending

            duration_str = random.choice(common.build_tuple('02-1-1.pv'))
            context.bot.send_message(chat_id=chat_id, text=duration_str)

            send_random_lines(context, chat_id, '02-1-2.pv')
            global is_s_listening
            is_s_listening = True  # Add handler to receive a success report.

            if duration_str[0].isdigit():
                timer_min = int(re.search(r'\d+', duration_str).group())
            else:
                timer_min = 2

            give_permission_to_start(message, context, timer_min)
            context.job_queue.run_once(ask_sf, timer_min * 60,
                                       context=chat_id, name=Constants.JOB_ASK_SF)


# If called, the handler will wait for the responses.
def warn_then_block(update: Update, context: CallbackContext):
    chat_id = update.effective_message.chat_id
    global is_waiting_response_yes, is_waiting_response_start

    # Send a simple warning message with no effect.
    remove_job_if_exists(Constants.JOB_DEMAND_RESPONSE, context)
    context.job_queue.run_once(demand_response, Constants.SEC_WAITING_RESPONSE, context=chat_id,
                               name=Constants.JOB_DEMAND_RESPONSE)
    is_waiting_response_yes = True
    is_waiting_response_start = True
    print('Waiting response for {:d}".'.format(Constants.SEC_WAITING_RESPONSE))

    # If responses are not received, block receiving messages as a punishment.
    remove_job_if_exists(Constants.JOB_WAIT_SHUTDOWN, context)
    context.job_queue.run_once(block_shortly, Constants.SEC_WAITING_SHUTDOWN, context=chat_id,
                               name=Constants.JOB_WAIT_SHUTDOWN)


def demand_response(context: CallbackContext) -> None:
    job = context.job
    # TODO: Play recorded voice occasionally.
    demanding_line = random.choice(common.build_tuple('demanding_response.pv'))
    context.bot.send_message(job.context, text=demanding_line)


def set_timer(message: telegram.Message, context: CallbackContext, duration_sec: int):
    chat_id = message.chat_id
    m, s = divmod(duration_sec, 60)
    if s:
        send_informative_message(chat_id, context, '{:d}분 {:d}초 타이머가 설정되었습니다.'.format(m, s), message)
    else:
        send_informative_message(chat_id, context, '{:d}분 타이머가 설정되었습니다.'.format(m), message)
    # Add a timer.
    remove_job_if_exists(Constants.JOB_TIMER, context)
    context.job_queue.run_once(go_off, duration_sec, context=chat_id, name=Constants.JOB_TIMER)
    print('Timer set for {}\''.format(duration_sec))


def set_termination_timer(message: telegram.Message, context: CallbackContext, duration_min: int) -> None:
    # Add a job to the queue.
    chat_id = message.chat_id
    seconds = duration_min * 60

    # Send an alert before the timer goes off.
    remove_job_if_exists(Constants.JOB_LITTLE_LEFT, context)
    context.job_queue.run_once(has_little_left, seconds - Constants.LITTLE_TIME_MIN * 60,
                               context=chat_id, name=Constants.JOB_LITTLE_LEFT)

    common.sleep_random_seconds(0.8, 1.2)
    set_timer(message, context, seconds)
    # The alarm goes off and the session will be terminated.
    inactivate(chat_id, context)


def send_informative_message(chat_id, context: CallbackContext, msg: str, message: telegram.Message = None):
    print("Bot: " + msg)
    if message:
        message.reply_text(text='`({})`'.format(msg), parse_mode=telegram.ParseMode.MARKDOWN_V2)
    else:
        context.bot.send_message(chat_id=chat_id, text='`({})`'.format(msg), parse_mode=telegram.ParseMode.MARKDOWN_V2)


def cancel_timer(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    job_removed = remove_job_if_exists(Constants.JOB_TIMER, context)
    msg = '타이머가 취소되었습니다.' if job_removed else '활성화된 타이머가 없습니다.'
    send_informative_message(message.chat_id, context, msg, message)


def give_orientation(update: Update, context: CallbackContext) -> None:
    msg = common.read_from_file('orientation.pv')
    context.bot.send_message(chat_id=update.effective_message.chat_id,
                             text=msg, parse_mode=telegram.ParseMode.MARKDOWN_V2)


def error(update: Updater, context: CallbackContext):
    # Log Errors caused by Updates
    logger.warning('Update {} caused error {}'.format(update, context.error))


def order_1(update: Update, context: CallbackContext):
    give_1(update, context)


def order_2(update: Update, context: CallbackContext):
    give_2(update, context)


def stop_receiving_sf(context: CallbackContext):
    remove_job_if_exists(Constants.JOB_ASK_SF, context)  # Don't ask.
    global is_s_listening, is_f_listening  # Don't listen.
    is_s_listening = False
    is_f_listening = False


def duration_successful(update: Update, context: CallbackContext):
    global is_s_listening, is_suppression_successful
    if is_s_listening:
        stop_receiving_sf(context)
        is_suppression_successful = True
        # TODO: Play recorded voice FREQUENTLY.
        global is_to_suppress
        chat_id = update.effective_message.chat_id

        if is_to_suppress:
            send_random_lines(context, chat_id, '02-0-s-0.pv')
        else:
            send_random_lines(context, chat_id, '02-1-s-0.pv')
        unlock_ordering()  # To receive new asking.


def duration_failed(update: Update, context: CallbackContext):
    # TODO: Play recorded voice occasionally.
    global is_to_suppress, is_f_listening
    if is_f_listening:
        stop_receiving_sf(context)
        chat_id = update.effective_message.chat_id
        if is_to_suppress:
            send_random_lines(context, chat_id, '02-0-f-0.pv')
        else:
            send_random_lines(context, chat_id, '02-1-f-0.pv')

        # A common direction: clean and take pictures
        common.sleep_random_seconds(2, 2.4)
        send_random_lines(context, chat_id, '02-0-f-1.pv')

        time.sleep(2.8)
        send_informative_message(chat_id, context, '데이터 수신을 차단합니다.')
        global is_active, reactivated_time
        blocked_sec = random.randint(3600 * 7, 3600 * 9)
        inactivate(chat_id, context, blocked_sec)


def block_shortly(context: CallbackContext) -> None:
    blocked_sec = random.choice((120, 240))
    inactivate(context.job.context, context, blocked_sec)
    print('Did not get a response. Sleep for {:d}\'.'.format(blocked_sec))


def activate_session(context: CallbackContext):
    print('Session activated.')
    # TODO: Remove global variables to run multiple bot threads.
    #  (https://python-telegram-bot.readthedocs.io/en/stable/telegram.ext.callbackcontext.html#telegram.ext.CallbackContext.chat_data)

    # Reset all the global variables.
    global is_active  # Especially, this one.
    is_active = True

    global is_waiting_response_yes, is_waiting_response_start
    is_waiting_response_yes = False
    is_waiting_response_start = False

    global is_allowed, denial_count
    is_allowed = True
    denial_count = 0

    global is_direction_given, is_to_suppress
    is_direction_given = False
    is_to_suppress = True

    global is_s_listening, is_f_listening, is_suppression_successful
    is_s_listening = False
    is_f_listening = False
    is_suppression_successful = False

    global reactivated_time
    reactivated_time = datetime.datetime.now()

    global rubbing_min, pause_min, repeat, cycle_number
    rubbing_min = 0
    pause_min = 0
    repeat = 0
    cycle_number = 0


def add_command_handlers():
    global dispatcher

    help_handler = CommandHandler('help', command_help)
    dispatcher.add_handler(help_handler)

    # Note: Disable privacy mode by /setprivacy to read "normal" messages.
    # (https://stackoverflow.com/a/67163946/17198283)
    response_handler = MessageHandler(Filters.text & (~ Filters.command), interpret_message)
    dispatcher.add_handler(response_handler)

    commands = common.build_tuple_of_tuples('help.pv')
    for number, help_item in enumerate(commands):
        command, desc = help_item
        if number == 0:
            order_1_handler = CommandHandler(command, order_1)
            dispatcher.add_handler(order_1_handler)
        if number == 1:
            order_2_handler = CommandHandler(command, order_2)
            dispatcher.add_handler(order_2_handler)

    # Add sf handlers.
    sup_command = common.build_tuple_of_tuples('duration_sf.pv')[1][0]
    duration_f_handler = CommandHandler(sup_command, duration_failed)
    dispatcher.add_handler(duration_f_handler)

    sup_command = common.build_tuple_of_tuples('duration_sf.pv')[0][0]
    duration_s_handler = CommandHandler(sup_command, duration_successful)
    dispatcher.add_handler(duration_s_handler)


def main():
    global dispatcher

    # Create the job in schedule.(https://stackoverflow.com/a/60867438/17198283)
    schedule.every().day.at("09:00").do(renew_allowing_rubbing)
    renew_allowing_thread = Thread(target=schedule_checker)
    renew_allowing_thread.daemon = True  # https://stackoverflow.com/a/11816038/17198283
    renew_allowing_thread.start()

    # Get the dispatcher to register handlers.
    updater = Updater(Constants.BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_error_handler(error)

    # Add basic handlers.
    dispatcher.add_handler(CommandHandler('start', give_orientation))
    dispatcher.add_handler(CommandHandler('cancel', cancel_timer))

    # Add the defined handlers.
    add_command_handlers()

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
