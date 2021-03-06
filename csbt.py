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
    SEC_SESSION_COOLDOWN = 3600
    LITTLE_TIME_MIN = 1

    JOB_TIMER = 'timer'
    JOB_LITTLE_LEFT = 'little_left'
    JOB_ACTIVATE = 'activate'
    JOB_INFORM_CYCLE_STATUS = 'inform_cycle_status'
    JOB_DECLARE_START = 'declare_start'
    JOB_ASK_SF = 'ask_sf'


# Whether to allow rubbing or not: refreshed daily.
is_allowed: bool = True
denial_count: int = 0

# Specifying behavior of rubbing
is_direction_given: bool = False
is_to_suppress: bool = True
is_sup_inter_recording: bool = False

# Activity sf handlers
is_s_listening: bool = False
is_f_listening: bool = False
is_duration_successful: bool = False

# Activity of a session
is_active: bool = True
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
    send_informative_message(chat_id, context, '????????? ????????? ????????? ??????????????????.')


def has_little_left(context: CallbackContext) -> None:
    chat_id = context.job.context
    send_informative_message(chat_id, context, '{:d}??? ???????????????.'.format(Constants.LITTLE_TIME_MIN))


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
        print("Direction unlocked: new directions can be given.")
    else:
        print("Direction already unlocked. Don't change the state.")


def lock_giving_direction() -> None:
    global is_direction_given
    if not is_direction_given:
        is_direction_given = True
        print("Direction locked: new directions won't be given.")
    else:
        print("Direction already locked. Don't change the state.")


def interpret_message(update: Update, context: CallbackContext) -> None:
    global is_direction_given

    message = update.effective_message
    message_content = message.text
    chat_id = message.chat_id
    try:
        if re.search("(???\s????|??????).*???.?[???????]$", message_content) and re.search("(??????|??????|??????)", message_content):
            # A message about duration. Equivalent to /2.
            give_2(update, context)
        elif re.search("\d.????.{0,6}(??????|??????|??????).*[????????????].*???.?[???????]$", message_content):
            # A message about simple directions
            duration_min = int(re.search(r'\d+', message_content).group())
            common.sleep_random_seconds(2.8, 3.2)
            send_go(context, chat_id)
            common.sleep_random_seconds()
            set_termination_timer(message, context, duration_min)
        elif ((re.search("??????.*(??????.*???.+|??????.+)[???????]$", message_content) or
               re.search("^(??????|??????).*\s((??????|??????|??????|???)|(??????|??????|??????)).*???.?[???????]$", message_content)) and
              not re.search("(???\s????|??????)", message_content)):
            # A message about posture. Equivalent to /1.
            give_1(update, context)
    except (IndexError, ValueError):
        contact = common.read_from_file('contact.pv')
        update.effective_message.reply_text('???????????? ????????? ??? ????????????. {}??? ????????? ???????????? ????????? ????????? ????????? ???????????????.'.format(contact))


def send_random_lines(chat_id, context: CallbackContext, filename: str, msg_before: str = None):
    phrase = random.choice(common.build_tuple_of_tuples(filename))
    for i, line in enumerate(phrase):
        common.sleep_random_seconds()
        if i == 0 and msg_before:  # The first line and a message to add before the first line
            context.bot.send_message(chat_id=chat_id, text=msg_before + line)
        else:
            context.bot.send_message(chat_id=chat_id, text=line)


def give_permission_to_start(message: telegram.Message, context: CallbackContext,
                             timer_min: int = 0, go_line: str = None):
    chat_id = message.chat_id

    common.sleep_random_seconds(2.8, 3.2)
    if go_line:
        context.bot.send_message(chat_id=chat_id, text=go_line)
    else:
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
    # Give the start direction.
    go_line = '??????'
    if common.get_random_bool():
        go_line += '???'
    context.bot.send_message(chat_id=chat_id, text=go_line)


def send_incomplete_msg(update: Update, context: CallbackContext):
    text = '?????? ?????? ????????? ???????????? ???????????????.'
    message = update.effective_message
    send_informative_message(message.chat_id, context, text, replied_message=message)


def send_inactive_msg(update: Update, context: CallbackContext):
    global reactivated_time

    hour = reactivated_time.strftime("%-H")
    minute = (reactivated_time + datetime.timedelta(minutes=1)).strftime("%-M")

    text = '???????????? ???????????????. {}??? {}?????? ?????? ??????????????????.'.format(hour, minute)
    chat_id = update.effective_message.chat_id
    send_informative_message(chat_id, context, text)


def inform_cycle_status(context: CallbackContext):
    global pause_min, repeat, cycle_number
    global is_sup_inter_recording
    chat_id = context.job.context

    cycle_number += 1
    send_informative_message(chat_id, context, '(????????? ????????? ????????? ??????????????????.)\n{:d}??? ??? ??????: {:d}?????? ??? {:d}?????? ??????'
                             .format(pause_min, repeat, cycle_number), is_parenthesis=False)
    common.sleep_random_seconds()

    stop_line = common.build_tuple('02-1-3.pv')[0]
    context.bot.send_message(chat_id=chat_id, text=stop_line)

    if is_sup_inter_recording:
        common.sleep_random_seconds()
        phrase = random.choice(common.build_tuple_of_tuples('02-0-3.pv'))
        for line in phrase:
            if '??????' in line:
                context.bot.send_message(chat_id=chat_id, text=line.format(cycle_number))
            else:
                context.bot.send_message(chat_id=chat_id, text=line)
            common.sleep_random_seconds()
    else:
        send_random_lines(chat_id, context, 'conditioning.pv')


def declare_start(context: CallbackContext):
    global rubbing_min
    message = context.job.context
    if isinstance(message, telegram.Message):
        chat_id = message.chat_id
        send_informative_message(chat_id, context, '{}??? ???????????? ?????????????????????.'.format(rubbing_min))
        common.sleep_random_seconds(0.8, 1.2)
        send_go(context, chat_id)


def ask_sf(context: CallbackContext):
    remove_job_if_exists(Constants.JOB_INFORM_CYCLE_STATUS, context)
    remove_job_if_exists(Constants.JOB_DECLARE_START, context)
    remove_job_if_exists(Constants.JOB_TIMER, context)
    remove_job_if_exists(Constants.JOB_LITTLE_LEFT, context)

    global is_to_suppress
    chat_id = context.job.context

    if is_to_suppress:
        global repeat
        send_informative_message(chat_id, context, '(????????? ????????? ????????? ??????????????????.)\n{:d}?????? ??? {:d}?????? ??????.'.format(repeat, repeat),
                                 is_parenthesis=False)
        time.sleep(0.8)
    else:
        send_random_lines(chat_id, context, '02-1-3.pv')
        common.sleep_random_seconds(1.2, 1.8)

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
    global is_active, reactivated_time
    global is_to_suppress, is_duration_successful
    message = update.effective_message
    chat_id = message.chat_id

    if is_allowed:
        if is_direction_given:
            send_incomplete_msg(update, context)
        elif not is_active:
            send_inactive_msg(update, context)
        else:
            lock_giving_direction()  # Prevent generating another direction.
            if is_duration_successful:
                # if successful, the naked status has been already given.
                is_naked = False
            else:
                is_naked = common.get_random_bool(0.33)

            if not is_duration_successful:  # if successful, the user has already been merged into the process.
                pause_sec = random.uniform(8, 13)
                send_informative_message(chat_id, context, '????????? ????????? ???????????????.\n(?????? ????????????: {:.2f}???)'.format(pause_sec),
                                         replied_message=message, is_parenthesis=False)

                fluctuated_pause_sec = pause_sec * random.uniform(0.95, 1.005)
                time.sleep(fluctuated_pause_sec)
                send_informative_message(chat_id, context, '????????? ????????? ?????????????????????.\n({:.2f}???)'.format(fluctuated_pause_sec),
                                         is_parenthesis=False)
                common.sleep_random_seconds()

            if is_naked:
                nudity_direction = random.choice(common.build_tuple('01-0.pv'))
                context.bot.send_message(chat_id=chat_id, text=nudity_direction)
                common.sleep_random_seconds(1.6, 2.4)

            # TODO: ?????? ?????? ??? /credits ??? ????????? ??????. ???, ?????? ?????? ?????? ?????? ??????. ?????? ?????? ????????????????????? ???.
            if is_naked:
                send_random_lines(chat_id, context, filename='01-1.pv', msg_before='????????? ??? ???????????? ')
            else:
                send_random_lines(chat_id, context, filename='01-1.pv')

            if nested:  # The duration is going to be given. Therefore, don't give start permission at this stage.
                # Set time to prepare.
                if is_naked:
                    additional_sec = 10 * random.randint(2, 5)
                else:
                    additional_sec = 10 * random.randint(0, 1)
                pause_sec = 60 + additional_sec

                # Compose the message text.
                if additional_sec > 0:
                    sec_str = ' {}???'.format(additional_sec)
                else:
                    sec_str = ''
                if is_naked:
                    text = '1???{} ??? ????????? ??? ??? ??????'.format(sec_str)
                else:
                    text = '1???{} ??? ????????? ?????? ?????????'.format(sec_str)

                # Send the message.
                common.sleep_random_seconds(1.6, 2.4)
                context.bot.send_message(chat_id=chat_id, text=text)
                # TODO: Timer messages should reply to the messages that define the timer.

                common.sleep_random_seconds()
                set_timer(message, context, pause_sec)
                send_random_lines(chat_id, context, 'conditioning.pv', msg_before='?????? ???????????? ')
                common.sleep_random_seconds()
                time.sleep(pause_sec)
            else:  # The duration is not going to be given. Start the session once ready.
                # Give a direction sometimes.
                if common.get_random_bool(0.7):
                    send_random_lines(chat_id, context, '01-2.pv')

                if is_duration_successful:  # If called from ask_sf, the following direction has already been given.
                    pass
                else:  # Give the post process direction at this stage, if the give_1 was called.
                    send_random_lines(chat_id, context, '01-3.pv')

                common.sleep_random_seconds(1.6, 2.4)
                go_line = '?????? ??? ???????????? ' + random.choice(common.build_tuple('01-4.pv')) + ' ?????????'
                give_permission_to_start(message, context, go_line=go_line)
    else:
        # Not allowed, but asked the command.
        global denial_count
        last_count = denial_count
        denial_count += 1
        print('New denial count: {:d}'.format(denial_count))

        if last_count == 0:
            common.sleep_random_seconds(0.4, 1.2)
            context.bot.send_message(chat_id=chat_id, text='??????')

            # TODO: Play recorded voice occasionally.
            send_random_lines(chat_id, context, 'dont-0.pv')
        elif last_count == 1:
            send_random_lines(chat_id, context, 'dont-1.pv')
        else:
            send_informative_message(chat_id, context, '????????? ????????? ???????????????.')
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

        opening_str = random.choice(('????????? ', '????????? ', ''))
        if is_to_suppress:  # Suppressing
            global rubbing_min, pause_min, repeat, cycle_number
            cycle_number = 0

            common.sleep_random_seconds(0.8, 1.2)  # Just after time's up. A longer delay is confusing.
            send_random_lines(chat_id, context, '02-0-0.pv', msg_before=opening_str)

            # TODO: Give directions to maintain a temperature.
            strings = random.choice(common.build_tuple_of_tuples('02-0-1.pv'))
            integers = []
            for value in strings:
                integers.append(int(value))
            rubbing_min, pause_min, repeat = integers
            duration_str = '{:d}??? ?????? ?????? ?????? {:d}??? ?????? {:d}?????? ??????'.format(rubbing_min, pause_min, repeat)
            context.bot.send_message(chat_id=chat_id, text=duration_str)
            common.sleep_random_seconds()

            send_random_lines(chat_id, context, '02-0-2.pv')
            common.sleep_random_seconds()

            # Configure variables for cycling.
            global is_f_listening
            is_f_listening = True  # Activate handler to receive a failure report.

            # To demand recordings between pauses or not, determining messages in inform_cycle_status
            global is_sup_inter_recording

            unit_interval = (rubbing_min + pause_min) * 60
            for i in range(repeat):
                firing_time = unit_interval * i
                context.job_queue.run_once(declare_start, firing_time,
                                           context=message, name=Constants.JOB_DECLARE_START)
                if i < repeat - 1:  # Other than the last cycle.
                    context.job_queue.run_once(inform_cycle_status, rubbing_min * 60 + firing_time,
                                               context=chat_id, name=Constants.JOB_INFORM_CYCLE_STATUS)
                    # context (object, optional) ??? Additional data needed for the callback function.
                    # https://python-telegram-bot.readthedocs.io/en/stable/telegram.ext.jobqueue.html#telegram.ext.JobQueue.run_monthly
            overall_duration = unit_interval * repeat - pause_min * 60 + 3
            context.job_queue.run_once(ask_sf, overall_duration, context=chat_id, name=Constants.JOB_ASK_SF)
        else:  # Rushing
            send_random_lines(chat_id, context, '02-1-0.pv', msg_before=opening_str)
            common.sleep_random_seconds(1.6, 2.4)  # Suspending

            # TODO: Give a direction not to reach a temperature.
            duration_str = random.choice(common.build_tuple('02-1-1.pv'))
            context.bot.send_message(chat_id=chat_id, text=duration_str)

            send_random_lines(chat_id, context, '02-1-2.pv')
            global is_s_listening
            is_s_listening = True  # Add handler to receive a success report.

            if duration_str[0].isdigit():
                timer_min = int(re.search(r'\d+', duration_str).group())
            else:
                timer_min = 2

            give_permission_to_start(message, context, timer_min)
            context.job_queue.run_once(ask_sf, timer_min * 60,
                                       context=chat_id, name=Constants.JOB_ASK_SF)


def set_timer(message: telegram.Message, context: CallbackContext, duration_sec: int):
    chat_id = message.chat_id

    m, s = divmod(duration_sec, 60)
    duration_str = ''
    if m:
        duration_str += '{:d}??? '.format(m)
    if s:
        duration_str += '{:d}??? '.format(s)
    duration_str += '???????????? ?????????????????????.'
    send_informative_message(chat_id, context, duration_str)

    # Add a timer.
    remove_job_if_exists(Constants.JOB_TIMER, context)
    context.job_queue.run_once(go_off, duration_sec, context=chat_id, name=Constants.JOB_TIMER)
    print('Timer set for {}\"'.format(duration_sec))


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


def send_informative_message(chat_id, context: CallbackContext, text: str,
                             replied_message: telegram.Message = None, is_parenthesis: bool = True):
    print("Bot: " + text)
    template = '`({})`' if is_parenthesis else '`{}`'
    if replied_message:
        replied_message.reply_text(text=template.format(text), parse_mode=telegram.ParseMode.MARKDOWN_V2)
    else:
        context.bot.send_message(chat_id=chat_id, text=template.format(text), parse_mode=telegram.ParseMode.MARKDOWN_V2)


def cancel_timer(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    job_removed = remove_job_if_exists(Constants.JOB_TIMER, context)
    text = '???????????? ?????????????????????.' if job_removed else '???????????? ???????????? ????????????.'
    send_informative_message(message.chat_id, context, text, replied_message=message)


def give_orientation(update: Update, context: CallbackContext) -> None:
    msg = common.read_from_file('orientation.pv')
    context.bot.send_message(chat_id=update.effective_message.chat_id, disable_web_page_preview=True,
                             text=msg, parse_mode=telegram.ParseMode.MARKDOWN_V2)


def error(update: Updater, context: CallbackContext):
    # Log Errors caused by Updates
    logger.warning('Update {} caused error {}'.format(update, context.error))


def order_1(update: Update, context: CallbackContext):
    give_1(update, context)


def order_2(update: Update, context: CallbackContext):
    give_2(update, context)


def stop_receiving_sf(context: CallbackContext):
    # Reset the job queue.
    remove_job_if_exists(Constants.JOB_TIMER, context)
    remove_job_if_exists(Constants.JOB_LITTLE_LEFT, context)
    remove_job_if_exists(Constants.JOB_INFORM_CYCLE_STATUS, context)
    remove_job_if_exists(Constants.JOB_DECLARE_START, context)
    remove_job_if_exists(Constants.JOB_ASK_SF, context)
    remove_job_if_exists(Constants.JOB_ACTIVATE, context)

    global is_s_listening, is_f_listening
    is_s_listening = False
    is_f_listening = False


def duration_successful(update: Update, context: CallbackContext):
    global is_s_listening, is_duration_successful
    if is_s_listening:
        stop_receiving_sf(context)
        is_duration_successful = True
        # TODO: Play recorded voice FREQUENTLY.
        global is_to_suppress
        chat_id = update.effective_message.chat_id

        if is_to_suppress:
            send_random_lines(chat_id, context, '02-0-s-0.pv')
        else:
            send_random_lines(chat_id, context, '02-1-s-0.pv')
        unlock_ordering()  # To receive new asking.


def duration_failed(update: Update, context: CallbackContext):
    # TODO: Play recorded voice occasionally.
    global is_to_suppress, is_f_listening
    if is_f_listening:
        stop_receiving_sf(context)
        chat_id = update.effective_message.chat_id
        if is_to_suppress:
            send_random_lines(chat_id, context, '02-0-f-0.pv')
        else:
            send_random_lines(chat_id, context, '02-1-f-0.pv')

        # A common direction: clean and take pictures
        common.sleep_random_seconds(3.2, 4)
        send_random_lines(chat_id, context, '02-0-f-1.pv')

        time.sleep(2.8)
        send_informative_message(chat_id, context, '????????? ????????? ???????????????.')
        global is_active, reactivated_time
        blocked_sec = random.randint(3600 * 7, 3600 * 9)
        inactivate(chat_id, context, blocked_sec)


def activate_session(context: CallbackContext):
    # TODO: Remove global variables to run multiple bot threads.
    #  (https://python-telegram-bot.readthedocs.io/en/stable/telegram.ext.callbackcontext.html#telegram.ext.CallbackContext.chat_data)

    # Reset all the global variables.
    global is_active  # Especially, this one.
    is_active = True

    global is_allowed, denial_count
    is_allowed = True
    denial_count = 0

    global is_direction_given, is_to_suppress, is_sup_inter_recording
    is_direction_given = False
    is_to_suppress = common.get_random_bool(0.9)  # i.e. 100% in the first session, 90% afterwards.
    is_sup_inter_recording = common.get_random_bool()  # i.e. 0% in the first session, 50% afterwards.

    global is_s_listening, is_f_listening, is_duration_successful
    is_s_listening = False
    is_f_listening = False
    is_duration_successful = False

    global reactivated_time
    reactivated_time = datetime.datetime.now()

    global rubbing_min, pause_min, repeat, cycle_number
    rubbing_min = 0
    pause_min = 0
    repeat = 0
    cycle_number = 0

    # Reset the job queue.
    remove_job_if_exists(Constants.JOB_TIMER, context)
    remove_job_if_exists(Constants.JOB_LITTLE_LEFT, context)
    remove_job_if_exists(Constants.JOB_INFORM_CYCLE_STATUS, context)
    remove_job_if_exists(Constants.JOB_DECLARE_START, context)
    remove_job_if_exists(Constants.JOB_ASK_SF, context)
    remove_job_if_exists(Constants.JOB_ACTIVATE, context)
    print('Session activated.')


def cheat_session(update: Update, context: CallbackContext):
    chat_id = update.effective_message.chat_id
    activate_session(context)
    text = random.choice(('For Adun!', 'En taro Adun.', 'En taro Tassadar.', 'Power overwhelming.'))
    send_informative_message(chat_id, context, text)


def add_command_handlers(dp: Updater.dispatcher):
    dp.add_handler(CommandHandler('start', give_orientation))
    dp.add_handler(CommandHandler('cancel', cancel_timer))
    dp.add_handler(CommandHandler('poweroverwhelming', cheat_session))

    help_handler = CommandHandler('help', command_help)
    dp.add_handler(help_handler)

    # Note: Disable privacy mode by /setprivacy to read "normal" messages.
    # (https://stackoverflow.com/a/67163946/17198283)
    response_handler = MessageHandler(Filters.text & (~ Filters.command), interpret_message)
    dp.add_handler(response_handler)

    commands = common.build_tuple_of_tuples('help.pv')
    for number, help_item in enumerate(commands):
        command, desc = help_item
        if number == 0:
            order_1_handler = CommandHandler(command, order_1)
            dp.add_handler(order_1_handler)
        if number == 1:
            order_2_handler = CommandHandler(command, order_2)
            dp.add_handler(order_2_handler)

    # Add sf handlers.
    sup_command = common.build_tuple_of_tuples('duration_sf.pv')[1][0]
    duration_f_handler = CommandHandler(sup_command, duration_failed)
    dp.add_handler(duration_f_handler)

    sup_command = common.build_tuple_of_tuples('duration_sf.pv')[0][0]
    duration_s_handler = CommandHandler(sup_command, duration_successful)
    dp.add_handler(duration_s_handler)


def main():
    # Create the job in schedule.(https://stackoverflow.com/a/60867438/17198283)
    schedule.every().day.at("09:00").do(renew_allowing_rubbing)
    renew_allowing_thread = Thread(target=schedule_checker)
    renew_allowing_thread.daemon = True  # https://stackoverflow.com/a/11816038/17198283
    renew_allowing_thread.start()

    # Get the dispatcher to register handlers.
    updater = Updater(Constants.BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_error_handler(error)

    # Add handlers.
    add_command_handlers(dispatcher)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
