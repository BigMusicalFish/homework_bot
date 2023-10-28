import json
import logging
import os
import requests
import telegram
import time

from telegram import Bot
from dotenv import load_dotenv
from http import HTTPStatus

load_dotenv()


PRACTICUM_TOKEN = os.getenv('pr_token')
TELEGRAM_TOKEN = os.getenv('tel_token')
TELEGRAM_CHAT_ID = os.getenv('tel_id')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверка доступности токенов и ID."""
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в чат."""
    try:
        logging.debug('Попытка отправки сообщения в telegram')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Отправка сообщения в telegram')
    except telegram.error.TelegramError as error:
        logging.error(f'Не удалось отправить сообщение в telegram: {error}')
        raise Exception(error)


def get_api_answer(timestamp):
    """Получить статус домашней работы из обновления."""
    current_time = timestamp or int(time.time())
    params = {'from_date': current_time}
    try:
        logging.debug('Попытка отправки запроса к эндпоинту API-сервиса')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logging.debug('Отправлен запрос к эндпоинту API-сервиса')
    except requests.ConnectionError:
        logging.error('Подключение к Интернету отсутствует')
        raise ConnectionError('Подключение к Интернету отсутствует')
    except Exception as error:
        logging.error(f'Эндпоинт недоступен.Ошибка от сервера: {error}')
        send_message(f'Эндпоинт недоступен. Ошибка от сервера: {error}')
    if response.status_code != HTTPStatus.OK:
        logging.error(f'Код ответа не 200: {response.status_code}')
        raise requests.exceptions.RequestException(
            f'Код ответа не 200: {response.status_cod}'
        )
    try:
        return response.json()
    except json.JSONDecodeError:
        logging.error('Сервер вернул невалидный ответ')
        send_message('Сервер вернул невалидный ответ')


def check_response(response):
    """Проверить валидность ответа."""
    try:
        homework = response['homeworks']
    except KeyError as error:
        logging.error(f'Ошибка доступа по ключу homeworks: {error}')
    if not isinstance(homework, list):
        logging.error('Homeworks не в виде списка')
        raise TypeError('Homeworks не в виде списка')
    return homework


def parse_status(homework):
    """Получить статус домашней работы."""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        logging.error('Неверный ответ сервера')
    homework_status = homework.get('status')
    verdict = ''
    if ((homework_status is None) or (
        homework_status == '')) or ((
            homework_status != 'approved') and (
            homework_status != 'rejected')):
        logging.error(f'Статус работы некорректен: {homework_status}')
        raise KeyError('Homeworks не в виде списка')
    if homework_status == 'rejected':
        verdict = HOMEWORK_VERDICTS['rejected']
    elif homework_status == 'approved':
        verdict = HOMEWORK_VERDICTS['approved']
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    logging.info('Запущен бот по проверке задания')
    if not check_tokens():
        logging.critical('Не все переменные окружения на месте')
        raise Exception('Не все переменные окружения на месте')
    current_timestamp = 1656890433
    old_homework_status = ''
    while True:
        try:
            all_homework = get_api_answer(current_timestamp)
            if len(all_homework['homeworks']) > 0:
                homework = check_response(all_homework)[0]
                homework_status = parse_status(homework)
                if homework_status != old_homework_status:
                    old_homework_status = homework_status
                    send_message(bot, homework_status)
                    logging.info('Сообщение отправлено')
                else:
                    logging.debug('Статус не изменился')
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
            send_message(bot, f'Сбой в работе программы: {error}')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(levelname)s, %(message)s',
        filename='program.log'
    )
    main()
