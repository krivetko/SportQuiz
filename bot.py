from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    ConversationHandler
)

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo
)

from datetime import (
    timedelta,
    datetime,
    date
)

from pytz import timezone
import pygsheets
import copy
import time

import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BUTTONS_SHOW, MAIN_MENU_SHOW, AUTH, WAIT_ANSWER, WAIT_MEDIA_ANSWER = range(5)

daily_tasks = {}
cached_participants = {}
cached_results = {}
results_to_upload = {}
right_answers = []

leaders = [ '212504240',
            '521812517',
            '208021168',
            '1208194227',
            '529972873',
            '1029658531',
            '367156590',
            '1198377474',
            '1224436440',
            '942251657',
            '1025225399',
            '172634974',
            '1775817232',
            '1140667290']

KRIVETKO = 212504240

admins = ['212504240',
        '208021168']

bonus_tasks = ['202209',
            '202216',
            '202223']

gc = pygsheets.authorize(service_file='service_account_credentials.json')
gSheet = gc.open("SGUSportsQuiz")
partSheet = gSheet.worksheet_by_title('Participants')
tasksSheet = gSheet.worksheet_by_title('Tasks')
resultsSheet = gSheet.worksheet_by_title('Results')

VALIDATION_GROUP = -1001473975596

# --------------------- Caching ---------------------
def cache_right_answers():
    right_answers.clear()
    answersSheet = gSheet.worksheet_by_title('Answers')
    answers = answersSheet.get_all_records(numericise_data=False)
    for answer in answers:
        right_answers.append(answer)

def cache_daily_tasks(datestr=None):
    tasks = tasksSheet.get_all_records(numericise_data=False)
    keysList = ['id', 'task', 'type', 'value', 'media', 'answer', 'date', 'answertype']
    if len(tasks) > 0:
        daily_tasks.clear()
        for task in tasks:
            if task['date'] == datestr or datestr is None:
                taskDict = {keysList[i] : task[keysList[i]] for i in range(len(keysList)) if task[keysList[i]] != ''}
                if len(task['id'].split('_')) == 1 and (task['sent'] == '1' and task['ended'] == '0'):
                # if len(task['id'].split('_')) == 1:
                    daily_tasks[task['id']] = taskDict
                elif task['id'].split('_')[0] in daily_tasks and len(task['id'].split('_')) != 1:
                    if 'seq' not in daily_tasks[task['id'].split('_')[0]]:
                        daily_tasks[task['id'].split('_')[0]]['seq'] = []
                    daily_tasks[task['id'].split('_')[0]]['seq'].append(taskDict)

def cache_ended_task(task_id):
    tasks = tasksSheet.get_all_records(numericise_data=False)
    keysList = ['id', 'task', 'type', 'value', 'media', 'answer', 'date', 'answertype']
    if len(tasks) > 0:
        for task in tasks:
            if task['id'].split('_')[0] == task_id:
                taskDict = {keysList[i] : task[keysList[i]] for i in range(len(keysList)) if task[keysList[i]] != ''}
                if len(task['id'].split('_')) == 1 and (task['sent'] == '1' and task['ended'] == '1'):
                    daily_tasks[task_id] = taskDict
                elif task['id'].split('_')[0] in daily_tasks:
                    if 'seq' not in daily_tasks[task_id]:
                        daily_tasks[task_id]['seq'] = []
                    daily_tasks[task_id]['seq'].append(taskDict)

def cache_participants():
    participants = partSheet.get_all_records(numericise_data=False)
    for user in participants:
        telegramId = user['Telegram Id']
        cached_participants[telegramId] = {}
        if user['UseName'] == '0':
            cached_participants[telegramId]['username'] = user['Nickname']
        else:
            cached_participants[telegramId]['username'] = user['FIO']
        for key in ['Admin', 'HasJoker']:
            cached_participants[telegramId][key] = user[key]

def cache_results():
    cached_results.clear()
    targetColumns = {}
    for key in daily_tasks.keys():
        foundCells = resultsSheet.find(pattern=key, matchEntireCell=True)
        if len(foundCells) > 0:
            targetColumns[key] = foundCells[0].col
    results = resultsSheet.get_all_values(include_tailing_empty=True, include_tailing_empty_rows=False)
    for row in results[1:]:
        if row[0] != '':
            cached_results[row[0]] = {key : row[(targetColumns[key] - 1)] for key in targetColumns.keys()}
            cached_results[row[0]]['joker'] = row[1]

def convert_media(taskDict):
    mediaList = taskDict.pop('media', None)
    if mediaList is not None:
        media = []
        for element in mediaList.split(';'):
            mediaDict = dict([element.split(':')])
            media_id = mediaDict.pop('Photo', None)
            if media_id is not None:
                media.append(InputMediaPhoto(media=media_id))
            else:
                media_id = mediaDict.pop('Video', None)
                if media_id is not None:
                    media.append(InputMediaVideo(media=media_id))
        taskDict['media'] = media

# --------------------- User's Properties checking ---------------------
def isAuthorized(user_id) -> bool:
    if str(user_id) in cached_participants:
        return True
    else:
        return False

def hasJoker(user_id) -> bool:
    if str(user_id) in cached_participants:
        if cached_participants[str(user_id)]['HasJoker'] == '1':
            return True
        else:
            return False
    else:
        return False

# --------------------- Command Handlers ---------------------
def start(update: Update, context: CallbackContext) -> None:
    if update.effective_chat.id != -1001203218883:
        if isAuthorized(update.effective_user.id):
            keyboard = [
                [
                    InlineKeyboardButton("РџСЂР°РІРёР»Р° РєРІРµСЃС‚Р°", callback_data='rules'),
                    InlineKeyboardButton("РўР°Р±Р»РёС†Р°-СЂРµР№С‚РёРЅРі", callback_data='rankings')
                ],
                [
                    InlineKeyboardButton("РћС‚РІРµС‚С‹ РЅР° Р·Р°РґР°РЅРёСЏ РїСЂРѕС€Р»РѕР№ РЅРµРґРµР»Рё", callback_data='faq')
                ],
                [
                    InlineKeyboardButton("Р—Р°РґР°РЅРёСЏ РЅР° СЃРµРіРѕРґРЅСЏ", callback_data='current_task'),
                    InlineKeyboardButton("Р§Р°С‚ РґР»СЏ СѓС‡Р°СЃС‚РЅРёРєРѕРІ", callback_data='chat')
                ],
                [
                    InlineKeyboardButton("РќР°С€ СЃРїРѕСЂС‚РёРІРЅС‹Р№ РєР°РЅР°Р» РІ Telegram", callback_data='youtube')
                ]

            ]
        else:
            keyboard = [
                [
                    InlineKeyboardButton("РђРІС‚РѕСЂРёР·РѕРІР°С‚СЊСЃСЏ", callback_data='auth')
                ]
            ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Р”РѕСЃС‚СѓРїРЅС‹Рµ РєРѕРјР°РЅРґС‹:', reply_markup=reply_markup)
        return BUTTONS_SHOW

def admin_send_message(update: Update, context: CallbackContext) -> None:
    # gc = pygsheets.authorize(service_file='service_account_credentials.json')
    # gSheet = gc.open("SGUSportsQuiz")
    # partSheet = gSheet.worksheet_by_title('Participants')
    foundCells = partSheet.find(pattern=str(update.effective_user.id), cols=(1, 1))
    if len(foundCells) > 0 and partSheet.cell((foundCells[0].row, 5)).value != "":
        for line in partSheet.get_all_records():
            if len(str(line.get('Telegram Id')))>0:
                try:
                    context.bot.send_message(chat_id=line.get('Telegram Id'), text=' '.join(context.args))
                except:
                    logging.info(line.get('Telegram Id'))
    else:
        context.bot.send_message(chat_id=update.effective_user.id, text='РќРµРёР·РІРµСЃС‚РЅР°СЏ РєРѕРјР°РЅРґР°')

def admin_send_message_to_user(update: Update, context: CallbackContext) -> None:
    foundCells = partSheet.find(pattern=str(update.effective_user.id), cols=(1, 1))
    if len(foundCells) > 0 and partSheet.cell((foundCells[0].row, 5)).value != "":
        context.bot.send_message(chat_id=context.args[0], text=' '.join(context.args[1:]))
        logging.info(context.args[0] + ': РћС‚РїСЂР°РІР»РµРЅРѕ СЃРѕРѕР±С‰РµРЅРёРµ - ' + ' '.join(context.args[1:]))

def send_task_by_id(update: Updater, context: CallbackContext) -> None:
    send_task(context, get_task(context.args[1]), context.args[0], hasJoker(update.effective_user.id))

def force_sync(update: Updater, context: CallbackContext) -> None:
    cache_right_answers()
    if len(daily_tasks.keys()) > 0:
        key = list(daily_tasks.keys())[0]
        datestr = daily_tasks[key]['date']
        if datestr != '':
            cache_daily_tasks(datestr)
            cache_participants()
            cache_results()
            context.bot.send_message(chat_id=update.effective_user.id, text='РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ РІС‹РїРѕР»РЅРµРЅР°! Р—Р°РїРёСЃРµР№ РІ СЃРїСЂР°РІРѕС‡РЅРёРєР°С…: daily_tasks - {}, cached_participants - {}, cached_results - {}'.format(len(daily_tasks.keys()), len(cached_participants.keys()), len(cached_results.keys())))
        else:
            context.bot.send_message(chat_id=update.effective_user.id, text='Р’ С‚РµРєСѓС‰РёС… РґРЅРµРІРЅС‹С… Р·Р°РґР°РЅРёСЏС… РЅРµ Р·Р°РґР°РЅР° РґР°С‚Р°! РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ РЅРµ РІС‹РїРѕР»РЅРµРЅР°')
    else:
        context.bot.send_message(chat_id=update.effective_user.id, text='РЎРїРёСЃРѕРє С‚РµРєСѓС‰РёС… РґРЅРµРІРЅС‹С… Р·Р°РґР°РЅРёР№ РїСѓСЃС‚! РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ РЅРµ РІС‹РїРѕР»РЅРµРЅР°')

def echo(update: Updater, context: CallbackContext) -> None:
    username = get_username(user_id=update.effective_user.id)
    if username is not None:
        context.bot.send_message(chat_id=update.effective_user.id, text=str(username) + '! Р”Р»СЏ РІР·Р°РёРјРѕРґРµР№СЃС‚РІРёСЏ СЃ Р±РѕС‚РѕРј РІРѕСЃРїРѕР»СЊР·СѓР№С‚РµСЃСЊ РєРѕРјР°РЅРґРѕР№ /start РёР»Рё РєРЅРѕРїРєР°РјРё, РїСЂРёРєСЂРµРїР»РµРЅРЅС‹РјРё Рє СЃРѕРѕР±С‰РµРЅРёСЏРј СЃ Р·Р°РґР°РЅРёСЏРјРё!')

# --------------------- Conversation Handlers ---------------------
def auth_start(update: Update, context: CallbackContext) -> int:

    update.callback_query.message.delete()
    context.bot.send_message(chat_id=update.effective_user.id, text='Р”Р»СЏ Р°РІС‚РѕСЂРёР·Р°С†РёРё РѕС‚РїСЂР°РІСЊС‚Рµ Р¤РРћ РёР»Рё РќРёРєРЅРµР№Рј, СѓРєР°Р·Р°РЅРЅС‹Рµ РїСЂРё СЂРµРіРёСЃС‚СЂР°С†РёРё:')
    return AUTH

def auth_end(update: Update, context: CallbackContext) -> int:

    FIO = update.message.text
    foundCells = partSheet.find(pattern=FIO, cols=(2,2))
    userFound = False
    if len(foundCells) > 0:
        context.bot.send_message(chat_id=update.effective_user.id, text='РЎРїР°СЃРёР±Рѕ Рё СѓРґР°С‡Рё РІ СЃРѕСЃС‚СЏР·Р°РЅРёРё, {}!'.format(FIO))
        partSheet.cell((foundCells[0].row,1)).value = update.effective_user.id
        userFound = True
    else:
        foundCells = partSheet.find(pattern=FIO, cols=(3,3))
        if len(foundCells) > 0:
            context.bot.send_message(chat_id=update.effective_user.id, text='РЎРїР°СЃРёР±Рѕ Рё СѓРґР°С‡Рё РІ СЃРѕСЃС‚СЏР·Р°РЅРёРё, {}!'.format(FIO))
            partSheet.cell((foundCells[0].row,1)).value = update.effective_user.id
            userFound = True
        else:
            context.bot.send_message(chat_id=update.effective_user.id, text='Рљ СЃРѕР¶Р°Р»РµРЅРёСЋ, РЅРµ СЃРјРѕРі РЅР°Р№С‚Рё Р’Р°СЃ РІ СЃРїРёСЃРєРµ СѓС‡Р°СЃС‚РЅРёРєРѕРІ. РџСЂРѕСЃСЊР±Р° РѕР±СЂР°С‚РёС‚СЊСЃСЏ Рє РѕСЂРіР°РЅРёР·Р°С‚РѕСЂСѓ!')

    text_to_krivetko = str(update.effective_user.id) + " : " + update.message.text + " : User found - " + str(userFound)
    logger.info(text_to_krivetko)
    context.bot.send_message(chat_id=KRIVETKO, text=text_to_krivetko)
    return ConversationHandler.END

def get_text_answer(update: Updater, context: CallbackContext) -> int:
    task_id = context.user_data['task_id'].split('_')[0]
    task = get_task(task_id)
    if task['answertype'] == 'media':
        context.bot.send_message(chat_id=update.effective_user.id, text='Р”Р°РЅРЅС‹Р№ РІРѕРїСЂРѕСЃ РЅРµ РїСЂРµРґРїРѕР»Р°РіР°РµС‚ С‚РµРєСЃС‚РѕРІРѕРіРѕ РѕС‚РІРµС‚Р°, РІРѕР·РјРѕР¶РЅРѕ РІС‹ РѕС€РёР±Р»РёСЃСЊ РєРЅРѕРїРєРѕР№ РґР»СЏ РѕС‚РІРµС‚Р° РЅР° Р·Р°РґР°РЅРёРµ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РѕС‚РІРµС‚РёС‚СЊ РµС‰Рµ СЂР°Р·, РёР»Рё Р·Р°РґР°Р№С‚Рµ РІРѕРїСЂРѕСЃ РІ С‡Р°С‚Рµ СѓС‡Р°СЃС‚РЅРёРєРѕРІ.')
        context.user_data.pop('task_id', None)
        context.user_data.pop('message_id', None)
        context.user_data.pop(task_id + 'seqAnswers', None)
        return ConversationHandler.END

    seq = context.user_data.pop(task_id + 'seq', None)
    if seq is not None:
        if task_id + 'seqAnswers' in context.user_data.keys():
            context.user_data[task_id + 'seqAnswers'].append(update.message.text.lower().strip())
        else:
            context.user_data[task_id + 'seqAnswers'] = [update.message.text.lower().strip()]
        task = seq.pop(0)
        if len(seq) > 0:
            context.user_data[task_id + 'seq'] = seq
        send_task(context, task, update.effective_user.id)
        return WAIT_ANSWER

    if task_id + 'seqAnswers' in context.user_data.keys():
        context.user_data[task_id + 'seqAnswers'].append(update.message.text.lower().strip())

    answerIsCorrect = validate_answer(task_id, update.message.text.lower(), context)
    if answerIsCorrect:
        context.bot.send_message(chat_id=update.effective_user.id, text='Р’Р°С€ РѕС‚РІРµС‚ РїСЂРёРЅСЏС‚.')
        mark_answer(str(update.effective_user.id), task_id, True)

        infotext = str(update.effective_user.id) + ': РєРѕСЂСЂРµРєС‚РЅС‹Р№ С‚РµРєСЃС‚РѕРІС‹Р№ РѕС‚РІРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ - ' + task_id + ': '
        if task_id + 'seqAnswers' in context.user_data.keys():
            infotext = infotext + ' '.join(context.user_data[task_id + 'seqAnswers'])
        else:
            infotext = infotext + update.message.text.lower()
        logging.info(infotext)

        context.user_data.pop('task_id', None)
        context.user_data.pop('message_id', None)
        context.user_data.pop(task_id + 'seqAnswers', None)

        return ConversationHandler.END
    else:
        mark_answer(str(update.effective_user.id), task_id, correctAnswer=False, approvalPending=True)
        context.bot.send_message(chat_id=update.effective_user.id, text='Р’Р°С€ РѕС‚РІРµС‚ РїСЂРёРЅСЏС‚.')
        infotext = str(update.effective_user.id) + ': РќР•РєРѕСЂСЂРµРєС‚РЅС‹Р№ С‚РµРєСЃС‚РѕРІС‹Р№ РѕС‚РІРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ (РѕС‚РїСЂР°РІР»РµРЅ РЅР° РІР°Р»РёРґР°С†РёСЋ) - ' + task_id + ': '
        if task_id + 'seqAnswers' in context.user_data.keys():
            infotext = infotext + ' '.join(context.user_data[task_id + 'seqAnswers'])
            validation_text = 'РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ - <b>' + get_username(update.effective_user.id) + '</b> ({})\nР’РѕРїСЂРѕСЃ - <b>в„–'.format(update.effective_user.id) + task_id.replace('2021', '') + '</b>\n' + 'РќРµ РѕР±СЂР°Р±РѕС‚Р°РЅРЅС‹Р№ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РѕС‚РІРµС‚: \n\n' + '\n'.join(context.user_data[task_id + 'seqAnswers'])
        else:
            infotext = infotext + update.message.text.lower()
            validation_text = 'РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ - <b>' + get_username(update.effective_user.id) + '</b> ({})\nР’РѕРїСЂРѕСЃ - <b>в„–'.format(update.effective_user.id) + task_id.replace('2021', '') + '</b>\n' + 'РќРµ РѕР±СЂР°Р±РѕС‚Р°РЅРЅС‹Р№ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РѕС‚РІРµС‚: \n\n' + update.message.text
        validation_kb = generate_validation_kb(update.effective_user.id, context.user_data['task_id'])
        logging.info(infotext)
        context.bot.send_message(chat_id=VALIDATION_GROUP, text=validation_text, reply_markup=validation_kb, parse_mode='HTML')
        context.user_data.pop('task_id', None)
        context.user_data.pop('message_id', None)
        context.user_data.pop(task_id + 'seqAnswers', None)
        return ConversationHandler.END

def get_media_answer(update: Updater, context: CallbackContext) -> int:
    task = get_task(context.user_data['task_id'].split('_')[0])
    if task['answertype'] == 'text':
        context.bot.send_message(chat_id=update.effective_user.id, text='Р”Р°РЅРЅС‹Р№ РІРѕРїСЂРѕСЃ С‚СЂРµР±СѓРµС‚ С‚РµРєСЃС‚РѕРІРѕРіРѕ РѕС‚РІРµС‚Р°, РІРѕР·РјРѕР¶РЅРѕ РІС‹ РѕС€РёР±Р»РёСЃСЊ РєРЅРѕРїРєРѕР№ РґР»СЏ РѕС‚РІРµС‚Р° РЅР° Р·Р°РґР°РЅРёРµ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РѕС‚РІРµС‚РёС‚СЊ РµС‰Рµ СЂР°Р·, РёР»Рё Р·Р°РґР°Р№С‚Рµ РІРѕРїСЂРѕСЃ РІ С‡Р°С‚Рµ СѓС‡Р°СЃС‚РЅРёРєРѕРІ.')
        context.user_data.pop('task_id', None)
        context.user_data.pop('message_id', None)
        return ConversationHandler.END

    context.bot.send_message(chat_id=update.effective_user.id, text='Р’Р°С€ РѕС‚РІРµС‚ РїСЂРёРЅСЏС‚.')
    validation_text = 'РћС‚РІРµС‚ РЅР° РІРѕРїСЂРѕСЃ - <b>в„–' + context.user_data['task_id'].split('_')[0].replace('2021', '') + '</b>\n' + 'РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ - <b>' + get_username(update.effective_user.id) + '</b> ({})'.format(update.effective_user.id)
    validation_kb = generate_validation_kb(update.effective_user.id, context.user_data['task_id'])
    infotext = str(update.effective_user.id) + ': РјРµРґРёР° РѕС‚РІРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РЅР° Р·Р°РґР°РЅРёРµ ' + context.user_data['task_id'] + ' РѕС‚РїСЂР°РІР»РµРЅ РЅР° РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ'
    context.bot.copy_message(chat_id=VALIDATION_GROUP, from_chat_id=update.message.chat.id, message_id=update.message.message_id, caption=validation_text, reply_markup=validation_kb, parse_mode='HTML')
    context.user_data.pop('task_id', None)
    context.user_data.pop('message_id', None)
    return ConversationHandler.END

def get_answer(update: Updater, context: CallbackContext) -> int:
    update.callback_query.answer()
    callbackData = update.callback_query.data
    task = get_task(callbackData[callbackData.index('_') + 1:].split('_')[0])
    if task is None:
        context.bot.send_message(chat_id=update.effective_user.id, text='РџРѕС…РѕР¶Рµ, РІСЂРµРјСЏ РїСЂРёРµРјР° РѕС‚РІРµС‚Р° СЌС‚РѕС‚ РІРѕРїСЂРѕСЃ РёСЃС‚РµРєР»Рѕ. РЈРґР°С‡Рё РІ СЃР»РµРґСѓСЋС‰РёС… СЌС‚Р°РїР°С… СЃРѕСЃС‚СЏР·Р°РЅРёСЏ!')
        return ConversationHandler.END
    context.user_data['task_id'] = callbackData[callbackData.index('_') + 1:]
    context.user_data['message_id'] = update.callback_query.message.message_id
    if 'sentMsgs' in context.user_data:
        context.user_data['sentMsgs'].pop(context.user_data['task_id'], None)
        if task['id'] + 'seqAnswers' not in context.user_data.keys():
            context.bot.send_message(chat_id=update.effective_user.id, text='РћС‚РїСЂР°РІСЊС‚Рµ РІР°С€ РѕС‚РІРµС‚ РёР»Рё РІРІРµРґРёС‚Рµ РєРѕРјР°РЅРґСѓ /cancel, РµСЃР»Рё С…РѕС‚РёС‚Рµ РµС‰Рµ РїРѕРґСѓРјР°С‚СЊ:')
        update.callback_query.message.edit_reply_markup()
    if 'seq' in task.keys() and task['id'] + 'seqAnswers' not in context.user_data.keys():
        context.user_data[task['id'] + 'seqAnswers'] = []
    return WAIT_ANSWER

def cancel(update: Updater, context: CallbackContext) -> int:
    task_id = context.user_data['task_id']
    message_id = context.user_data['message_id']
    context.bot.editMessageReplyMarkup(chat_id=update.effective_user.id, message_id=message_id, reply_markup=generate_answer_kb(task_id, hasJoker(update.effective_user.id)))
    context.user_data['sentMsgs'][task_id] = message_id
    context.user_data.pop('task_id', None)
    context.user_data.pop('message_id', None)
    context.user_data.pop('seq', None)
    task = get_task(task_id.split('_')[0])
    if 'seq' in task.keys():
        context.user_data[task_id.split('_')[0] + 'seq'] = task.pop('seq', None)
    context.bot.send_message(chat_id=update.effective_user.id, text='РџРѕРїС‹С‚РєР° РѕС‚РІРµС‚Р° РѕС‚РјРµРЅРµРЅР°. Р”Р»СЏ РїРѕРІС‚РѕСЂРЅРѕР№ РїРѕРїС‹С‚РєРё РµС‰Рµ СЂР°Р· Р·Р°РїСЂРѕСЃРёС‚Рµ Р·Р°РґР°РЅРёСЏ РЅР° СЃРµРіРѕРґРЅСЏ РёР· РіР»Р°РІРЅРѕРіРѕ РјРµРЅСЋ.')
    return ConversationHandler.END

# --------------------- Keyboard Generators ---------------------
def generate_answer_kb(task_id, joker=False):
    keyboard = [
        [
            InlineKeyboardButton("РћС‚РІРµС‚РёС‚СЊ", callback_data='task_' + task_id)
        ]
    ]
    if joker and (task_id not in bonus_tasks):
        keyboard[0].append(InlineKeyboardButton("РСЃРїРѕР»СЊР·РѕРІР°С‚СЊ Р”Р¶РѕРєРµСЂ!", callback_data='jkr_' + task_id))
    return InlineKeyboardMarkup(keyboard)

def generate_validation_kb(user_id, task_id):
    keyboard = [
        [
            InlineKeyboardButton("РџСЂРёРЅСЏС‚СЊ РѕС‚РІРµС‚", callback_data='accept_' + str(user_id) + '_' + task_id),
            InlineKeyboardButton("РћС‚РєР»РѕРЅРёС‚СЊ РѕС‚РІРµС‚", callback_data='decline_' + str(user_id) + '_' + task_id)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --------------------- Inline Buttons Functions ---------------------
def accept(update: Updater, context: CallbackContext):
    callbackData = update.callback_query.data.split('_')
    user_id = callbackData[1]
    task_id = callbackData[2]
    mark_answer(user_id, task_id, True)
    attrList = ['username', 'first_name', 'last_name']
    userinfo = {k : update.callback_query.from_user[k] for k in attrList if hasattr(update.callback_query.from_user, k)}
    username = userinfo.pop('username', None)
    if username is not None:
        usertext = '@' + str(username)
    else:
        firstlastname = [userinfo.pop('first_name', None), userinfo.pop('last_name', None)]
        usertext = ' '.join([elem for elem in firstlastname if elem is not None])
    if update.callback_query.message.text is not None:
        newText = update.callback_query.message.text + '\n<b>РћС‚РІРµС‚ РїСЂРёРЅСЏС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј ' + usertext + '</b>'
        context.bot.edit_message_text(message_id=update.callback_query.message.message_id, chat_id=update.callback_query.message.chat.id, text=newText, parse_mode='HTML', reply_markup=None)
    else:
        newText = update.callback_query.message.caption + '\n<b>РћС‚РІРµС‚ РїСЂРёРЅСЏС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј ' + usertext + '</b>'
        context.bot.edit_message_caption(message_id=update.callback_query.message.message_id, chat_id=update.callback_query.message.chat.id, caption=newText, parse_mode='HTML', reply_markup=None)
    update.callback_query.answer()


def decline(update: Updater, context: CallbackContext):
    callbackData = update.callback_query.data.split('_')
    user_id = callbackData[1]
    task_id = callbackData[2]
    mark_answer(user_id, task_id, False)
    attrList = ['username', 'first_name', 'last_name']
    userinfo = {k : update.callback_query.from_user[k] for k in attrList if hasattr(update.callback_query.from_user, k)}
    username = userinfo.pop('username', None)
    if username is not None:
        usertext = '@' + str(username)
    else:
        firstlastname = [userinfo.pop('first_name', None), userinfo.pop('last_name', None)]
        usertext = ' '.join([elem for elem in firstlastname if elem is not None])
    if update.callback_query.message.text is not None:
        newText = update.callback_query.message.text + '\n<b>РћС‚РІРµС‚ РѕС‚РєР»РѕРЅРµРЅ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј ' + usertext + '</b>'
        context.bot.edit_message_text(message_id=update.callback_query.message.message_id, chat_id=update.callback_query.message.chat.id, text=newText, parse_mode='HTML', reply_markup=None)
    else:
        newText = update.callback_query.message.caption + '\n<b>РћС‚РІРµС‚ РѕС‚РєР»РѕРЅРµРЅ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј ' + usertext + '</b>'
        context.bot.edit_message_caption(message_id=update.callback_query.message.message_id, chat_id=update.callback_query.message.chat.id, caption=newText, parse_mode='HTML', reply_markup=None)
    update.callback_query.answer()

def button(update: Update, context: CallbackContext) -> int:

    query = update.callback_query
    query.answer()
    if query.data == 'rules':
        rulesFile = open(r"res/rules.txt","r", encoding='utf-8')
        message_id = update.callback_query.message.message_id
        context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
        context.bot.send_message(chat_id=update.effective_user.id, text=rulesFile.read(), parse_mode='HTML')
        rulesFile.close()
    elif query.data == 'faq':
        message_id = update.callback_query.message.message_id
        context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
        for answer in right_answers:
            if answer.get('type', None) is not None:
                if answer['type'] == 'photo':
                    context.bot.send_photo(chat_id=update.effective_chat.id, photo=answer['link'])
                elif answer['type'] == 'video':
                    context.bot.send_video(chat_id=update.effective_chat.id, video=answer['link'])
                elif answer['type'] == 'animation':
                    context.bot.send_animation(chat_id=update.effective_chat.id, animation=answer['link'])

    elif query.data == 'rankings':
        message_id = update.callback_query.message.message_id
        context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
        context.bot.send_message(chat_id=update.effective_user.id, text='Р РµР·СѓР»СЊС‚Р°С‚С‹ СЂР°Р·РјРµС‰РµРЅС‹ РЅР° СЂРµСЃСѓСЂСЃРµ: <a href="https://docs.google.com/spreadsheets/d/1JOvqt1zBM75v_ikOAkeA1d8c66eGPhD2-du2uxOzww8/edit?usp=sharing">РўР°Р±Р»РёС†Р° Р»РёРґРµСЂРѕРІ</a>', parse_mode='HTML')
    elif query.data == 'youtube':
        message_id = update.callback_query.message.message_id
        context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
        context.bot.send_message(chat_id=update.effective_user.id, text='<a href="https://t.me/+GgOY2lsHM1Q1YzYy">РќР°С€ СЃРїРѕСЂС‚РёРІРЅС‹Р№ РєР°РЅР°Р» РІ Telegram</a>', parse_mode='HTML')
    elif query.data == 'current_task':
        message_id = update.callback_query.message.message_id
        context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
        # tempMessage = context.bot.send_message(chat_id=update.effective_user.id, text='РџСЂРѕРІРµСЂСЏСЋ Р°РєС‚РёРІРЅС‹Рµ Р·Р°РґР°РЅРёСЏ, СЌС‚Рѕ РјРѕР¶РµС‚ Р·Р°РЅСЏС‚СЊ РЅРµРєРѕС‚РѕСЂРѕРµ РІСЂРµРјСЏ')
        if (len(daily_tasks) > 0) and (str(update.effective_user.id) in leaders):
            tasks = []
            for key in daily_tasks.keys():
                if cached_results[str(update.effective_user.id)][key] == '':
                    tasks.append(get_task(key))
            joker = hasJoker(update.effective_user.id)
            for task in tasks:
                send_task(context, task, update.effective_user.id, joker)
        else:
            context.bot.send_message(chat_id=update.effective_user.id, text='РќР° СЃРµРіРѕРґРЅСЏ Р·Р°РґР°РЅРёР№ РЅРµС‚!')

        # try:
        #     tempMessage.delete()
        # except:
        #     logger.info('РќРµ СѓРґР°Р»РѕСЃСЊ СѓРґР°Р»РёС‚СЊ СЃРѕРѕР±С‰РµРЅРёРµ ' + str(tempMessage.message_id) + ' Сѓ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ ' + str(update.effective_user.id))

    elif query.data == 'chat':
        secret_chat_id = '-1001203218883'
        invite_link = context.bot.export_chat_invite_link(chat_id=secret_chat_id)
        if invite_link:
            query.message.delete()
            context.bot.send_message(chat_id=update.effective_user.id, text='Р”РѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ РІ С‡Р°С‚ СѓС‡Р°СЃС‚РЅРёРєРѕРІ! РЎСЃС‹Р»РєР°: {}'.format(invite_link))

def use_joker(update: Updater, context: CallbackContext) -> None:
    update.callback_query.answer()
    if datetime.date(datetime.today()) >= date(2022, 6, 20):
        context.bot.send_message(chat_id=update.effective_user.id, text='Р”Р¶РѕРєРµСЂ Р±РѕР»СЊС€Рµ РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РёСЃРїРѕР»СЊР·РѕРІР°РЅ РІ СЂР°РјРєР°С… СЌС‚РѕРіРѕ РєРІРµСЃС‚Р°!')
    elif datetime.today().isoweekday() == 7:
        context.bot.send_message(chat_id=update.effective_user.id, text='Р”Р¶РѕРєРµСЂ РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РёСЃРїРѕР»СЊР·РѕРІР°РЅ РІ РІРѕСЃРєСЂРµСЃРµРЅСЊРµ!')
    else:
        task_id = update.callback_query.data.split('_')[1]
        userKey = str(update.effective_user.id)
        if userKey in cached_participants.keys():
            if cached_participants[userKey]['HasJoker'] == '1':
                if task_id in daily_tasks.keys():
                    cached_participants[userKey]['HasJoker'] = '0'
                    cached_results[userKey]['joker'] = task_id
                    if userKey in results_to_upload.keys():
                        results_to_upload[userKey]['joker'] = task_id
                    else:
                        results_to_upload[userKey] = {}
                        results_to_upload[userKey]['joker'] = task_id
                    context.bot.send_message(chat_id=update.effective_user.id, text='Р”Р¶РѕРєРµСЂ Р±СѓРґРµС‚ РёСЃРїРѕР»СЊР·РѕРІР°РЅ РїСЂРё Р·Р°С‡РµС‚Рµ РѕС‚РІРµС‚Р° РЅР° РІРѕРїСЂРѕСЃ!')
                    notifyText = '{}: РСЃРїРѕР»СЊР·РѕРІР°РЅ РґР¶РѕРєРµСЂ РґР»СЏ Р·Р°РґР°РЅРёСЏ - {}'.format(update.effective_user.id, task_id)
                    logging.info(notifyText)
                    send_message_to_krivetko(context, notifyText)
                    if 'sentMsgs' in context.user_data:
                        for key in context.user_data['sentMsgs'].keys():
                            context.bot.edit_message_reply_markup(chat_id=update.effective_user.id, message_id=context.user_data['sentMsgs'][key], reply_markup=generate_answer_kb(key, False))
                else:
                    context.bot.send_message(chat_id=update.effective_user.id, text='Р”Р¶РѕРєРµСЂ РјРѕР¶РµС‚ Р±С‹С‚СЊ РёСЃРїРѕР»СЊР·РѕРІР°РЅ С‚РѕР»СЊРєРѕ РЅР° Р·Р°РґР°РЅРёСЏС… С‚РµРєСѓС‰РµРіРѕ СЌС‚Р°РїР°!')
            else:
                context.bot.send_message(chat_id=update.effective_user.id, text='РџРѕС…РѕР¶Рµ РґР¶РѕРєРµСЂ СѓР¶Рµ Р±С‹Р» РёСЃРїРѕР»СЊР·РѕРІР°РЅ Р’Р°РјРё СЂР°РЅРµРµ.')
        else:
            context.bot.send_message(chat_id=update.effective_user.id, text='РРЅС„РѕСЂРјР°С†РёСЏ Рѕ РґРѕСЃС‚СѓРїРЅРѕРј РґР¶РѕРєРµСЂРµ РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚. РџСЂРѕСЃСЊР±Р° РѕР±СЂР°С‚РёС‚СЊСЃСЏ Рє РѕСЂРіР°РЅРёР·Р°С‚РѕСЂР°Рј!')

# --------------------- General Purpose Utilities ---------------------
def mark_answer(user_id, task_id, correctAnswer=False, approvalPending=False):
    # logging.info(task_id)
    task=get_task(task_id.split('_')[0])
    if task is None:
        cache_ended_task(task_id.split('_')[0])
        task=get_task(task_id.split('_')[0])
        logging.info(task)
    if user_id not in results_to_upload.keys():
        results_to_upload[user_id] = {}
    if not correctAnswer:
        incorrectValue = 0
        if approvalPending == True:
            incorrectValue = -1
        if task['id'] in cached_results[user_id].keys():
            cached_results[user_id][task['id']] = incorrectValue
        results_to_upload[user_id][task['id']] = incorrectValue
    else:
        if cached_results[user_id]['joker'] == task['id']:
            if task['id'] in cached_results[user_id].keys():
                cached_results[user_id][task['id']] = int(task['value']) * 2
            results_to_upload[user_id][task['id']] = int(task['value']) * 2
        else:
            if task['id'] in cached_results[user_id].keys():
                cached_results[user_id][task['id']] = int(task['value'])
            results_to_upload[user_id][task['id']] = int(task['value'])

def get_username(user_id):
    if str(user_id) in cached_participants:
        return cached_participants[str(user_id)]['username']
    else:
        return None

def get_task(task_id):
    if task_id in daily_tasks:
        taskDict = copy.deepcopy(daily_tasks[task_id])
        convert_media(taskDict)
        return taskDict
    else:
        return None

def send_task(context, task, user_id, joker=False):
    media = task.pop('media', None)
    text = task.pop('task', None)
    value = task.pop('value', None)
    if value is not None:
        text = text + '\n(<b>РЎС‚РѕРёРјРѕСЃС‚СЊ: ' + value + (' Р±Р°Р»Р»РѕРІ' if int(value)> 4 else ' Р±Р°Р»Р»Р°') + '</b>)'
    if media is not None:
        context.bot.send_media_group(chat_id=user_id, media=media)
    seq = task.pop('seq', None)
    if seq is not None:
        for seqTask in seq:
            convert_media(seqTask)
        context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')
        if media is not None:
            context.bot.send_media_group(chat_id=user_id, media=media)
        task = seq.pop(0)
        context.user_data[task['id'].split('_')[0] + 'seq'] = seq
        context.user_data[task['id'].split('_')[0] + 'seqQuestionsToSend'] = len(seq)
        send_task(context, task, user_id, joker)
    else:
        seqQuestionsToSend = context.user_data.pop(task['id'].split('_')[0] + 'seqQuestionsToSend', None)
        sentMessage = None
        if seqQuestionsToSend is not None:
            #if seqQuestionsToSend == 2 or seqQuestionsToSend == 3: # Р’ СЃРµСЂРёРё 3-4 Р·Р°РґР°РЅРёСЏ, РѕРґРЅРѕ СѓР¶Рµ РЅР°РїСЂР°РІР»РµРЅРѕ. РџРѕСЌС‚РѕРјСѓ С‚РѕР»СЊРєРѕ РїСЂРё РґРІСѓС… Рё С‚СЂРµС… РѕСЃС‚Р°РІС€РёС…СЃСЏ РїРѕРєР°Р·С‹РІР°РµРј РєРЅРѕРїРєРё
            sentMessage = context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML', reply_markup=generate_answer_kb(task['id'], joker))
            #else:
            #    context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML')

            context.user_data[task['id'].split('_')[0] + 'seqQuestionsToSend'] = seqQuestionsToSend - 1
        else:
            sentMessage = context.bot.send_message(chat_id=user_id, text=text, parse_mode='HTML', reply_markup=generate_answer_kb(task['id'], joker))
        if sentMessage is not None:
            if 'sentMsgs' not in context.user_data:
                context.user_data['sentMsgs'] = {}
            context.user_data['sentMsgs'][task['id']] = sentMessage.message_id

def validate_answer(task_id, answer, context):
    task = get_task(task_id)
    if task is not None:
        if task_id + 'seqAnswers' in context.user_data.keys():
            #added 05.06.2022
            if len(task['seq']) > 0:
                answers = context.user_data[task_id + 'seqAnswers']
                if len(answers) == 0 or len(answers) != len(task['seq']):
                    logging.info('РјР°Р»Рѕ РѕС‚РІРµС‚РѕРІ')
                    logging.info(answer)
                    return False
                else:
                    correct_answers = [seq_task['answer'].split(';') for seq_task in task['seq']]
                    logging.info(correct_answers)
                    correct = 0
                    for i in range(len(answers)):
                        if answers[i] in correct_answers[i]:
                            correct += 1
                    logging.info('correct: {}'.format(correct))
                    if correct == len(correct_answers):
                        return True
                    else:
                        return False

            #answers = [a for a in task['answer'].split(';')]
            #if answers == context.user_data[task_id + 'seqAnswers']:
            #    return True
            #else:
            #    return False
        answers = {a for a in task['answer'].split(';')}
        if ' '.join(answer.split()) in answers:
            return True
        else:
            return False
    else:
        return False

def send_message_to_krivetko(context, message):
    for id in admins:
        context.bot.send_message(chat_id=id, text=message)

def google_sync(context: CallbackContext):
    logging.info('РќР°С‡Р°Р»Рѕ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё')
    if len(results_to_upload.keys()) > 0:
        for key in results_to_upload.keys():
            foundResultRow = resultsSheet.find(pattern=key, matchEntireCell=True)
            foundPart = partSheet.find(pattern=key, matchEntireCell=True)
            for resultKey in results_to_upload[key]:
                if resultKey == 'joker':
                    if len(foundPart) > 0:
                        partSheet.update_value((foundPart[0].row, 6), '0')
                    if len(foundResultRow) > 0:
                        resultsSheet.update_value((foundResultRow[0].row, 2), results_to_upload[key]['joker'])
                else:
                    if len(foundResultRow) > 0:
                        foundResultCol = resultsSheet.find(pattern=resultKey, matchEntireCell=True)
                        if len(foundResultCol) > 0:
                             resultsSheet.update_value((foundResultRow[0].row, foundResultCol[0].col), results_to_upload[key][resultKey])
            logging.info('РЎРёРЅС…СЂРѕРЅРёР·РёСЂРѕРІР°РЅР° РёРЅС„РѕСЂРјР°С†РёСЏ РїРѕ user_id - ' + key)
            logging.info(results_to_upload[key])
        results_to_upload.clear()
        if len(daily_tasks.keys()) > 0:
            key = list(daily_tasks.keys())[0]
            datestr = daily_tasks[key]['date']
            if datestr != '':
                cache_daily_tasks(datestr)
                cache_participants()
                cache_results()
    else:
        logging.info('РЎРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ РЅРµ С‚СЂРµР±СѓРµС‚СЃСЏ')

# Jobs

def send_daily_tasks(context: CallbackContext):
    partRows = partSheet.get_all_values(include_tailing_empty = False, include_tailing_empty_rows = False)
    partRows = partRows[1:]

    newTasksRow = tasksSheet.find(pattern=context.job.context['date'], matchEntireCell=True)
    for task in newTasksRow:
        tasksSheet.update_value((task.row, 8), '1')
    if context.job.context['prev_date'] is not None:
        oldTasksRow = tasksSheet.find(pattern=context.job.context['prev_date'], matchEntireCell=True)
        for task in oldTasksRow:
            tasksSheet.update_value((task.row, 9), '1')

    cache_daily_tasks(context.job.context['date'])
    cache_participants()
    cache_results()
    cache_right_answers()

    itemsSent = 0
    send_message_to_krivetko(context, 'РќР°С‡Р°С‚Р° РѕС‚РїСЂР°РІРєР° СѓРІРµРґРѕРјР»РµРЅРёР№.')
    for participant in partRows:
        if (participant[0] != '') and (str(participant[0]) in leaders):
        #if (participant[0] != ''):
            if participant[3] == '1':
                username = participant[1]
            else:
                username = participant[2]
            try:
                context.bot.send_message(chat_id=participant[0], text='РџСЂРёРІРµС‚СЃС‚РІСѓСЋ, {}! Р”РѕСЃС‚СѓРїРЅС‹ РЅРѕРІС‹Рµ Р·Р°РґР°РЅРёСЏ. Р”Р»СЏ РїСЂРѕСЃРјРѕС‚СЂР° РїСЂРѕС€Сѓ РІС‹РїРѕР»РЅРёС‚СЊ РєРѕРјР°РЅРґСѓ /start Рё РІС‹Р±СЂР°С‚СЊ РїСѓРЅРєС‚ <b>Р—Р°РґР°РЅРёСЏ РЅР° СЃРµРіРѕРґРЅСЏ</b>'.format(username), parse_mode='HTML')
                itemsSent = itemsSent + 1
                if itemsSent > 30:
                    send_message_to_krivetko(context, 'РћС‚РїСЂР°РІР»РµРЅРѕ 30 СЃРѕРѕР±С‰РµРЅРёР№.')
                    itemsSent = 0
            except:
                send_message_to_krivetko(context, '{} : СѓРІРµРґРѕРјР»РµРЅРёРµ Рѕ РЅРѕРІС‹С… Р·Р°РґР°РЅРёСЏС… РЅРµ РѕС‚РїСЂР°РІР»РµРЅРѕ!'.format(str(participant[0]) + '(' + username +')'))
    if itemsSent > 0:
        send_message_to_krivetko(context, 'РћС‚РїСЂР°РІР»РµРЅРѕ {} СЃРѕРѕР±С‰РµРЅРёР№.'.format(itemsSent))

def main():

    updater = Updater(token='', use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler('sendmsg', admin_send_message))
    dispatcher.add_handler(CommandHandler('sync', force_sync))
    dispatcher.add_handler(CommandHandler('sendusermsg', admin_send_message_to_user))
    dispatcher.add_handler(CommandHandler('sendtaskbyid', send_task_by_id))

    auth_button_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(auth_start, pattern='^auth$')],
        states={
            AUTH: [MessageHandler(Filters.text & (~Filters.command), auth_end)]
        },
        fallbacks=[],
        per_user=True
    )
    dispatcher.add_handler(auth_button_handler)

    answer_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(get_answer, pattern='^task_.*')],
        states={
            WAIT_ANSWER: [
                CallbackQueryHandler(get_answer, pattern='^task_.*'),
                MessageHandler(Filters.text & (~Filters.command), get_text_answer),
                MessageHandler(Filters.video | Filters.photo | Filters.document, get_media_answer)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True
    )
    dispatcher.add_handler(answer_handler)

    joker_handler = CallbackQueryHandler(use_joker, pattern='jkr_.*')
    dispatcher.add_handler(joker_handler)

    start_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            BUTTONS_SHOW: [CallbackQueryHandler(button)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    dispatcher.add_handler(start_handler)

    accept_answer_handler = CallbackQueryHandler(accept, pattern='^accept_.*')
    dispatcher.add_handler(accept_answer_handler)
    decline_answer_handler = CallbackQueryHandler(decline, pattern='^decline_.*')
    dispatcher.add_handler(decline_answer_handler)

    # echo_handler = MessageHandler(Filters.text & (~Filters.command), echo)
    # dispatcher.add_handler(echo_handler)

    tasksRows = tasksSheet.get_all_values(include_tailing_empty = False, include_tailing_empty_rows = False)
    tasksRows = tasksRows[1:]
    if len(daily_tasks.keys()) == 0:
        cache_daily_tasks()
    cache_participants()
    cache_results()
    cache_right_answers()
    dates = sorted(list({datetime.strptime(row[6], '%d.%m.%Y') for row in tasksRows if len(row) > 6 and row[8] != '1' and row[6] != ''}))
    prevDate = None
    for date in dates:
        contextObj = {}
        contextObj['date'] = date.strftime('%d.%m.%Y')
        contextObj['prev_date'] = prevDate
        j = updater.job_queue.run_once(send_daily_tasks, date + timedelta(hours=5), context=contextObj)
        prevDate = date.strftime('%d.%m.%Y')

    updater.job_queue.run_repeating(google_sync, 300)
    # exact_time = datetime(2021,2,19,3,35,0)
    # j = updater.job_queue.run_once(send_message_to_krivetko, exact_time)

    updater.start_polling()

    updater.idle()

if __name__ == '__main__':
    main()
