import logging
import os
import sys
import time
from http import HTTPStatus

import telegram
import requests
from requests.exceptions import RequestException
from dotenv import load_dotenv

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PR_TOKEN')
TELEGRAM_TOKEN = os.getenv('TEL_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TEL_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности токенов и ID."""
    return all([TELEGRAM_TOKEN, PRACTICUM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в чат."""
    try:
        logging.debug(f"Начало отправки сообщения: {message}")
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение в чат {TELEGRAM_CHAT_ID}: {message}')
    except Exception as error:
        logging.error(f'Ошибка отправки сообщения в Telegramm: {error}')


def get_api_answer(timestamp):
    """Получить статус домашней работы из обновления."""
    params = {'url': ENDPOINT, 'headers': HEADERS,
              'params': {'from_date': timestamp}}
    try:
        logging.info(
            'Начало запроса: url = {url}, headers = {headers},'
            'params = {params}'.format(**params))
        homework_statuses = requests.get(**params)
    except RequestException as error:
        raise exceptions.OrigExceptError(f'Ошибка при запросе к API: {error}')
    else:
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.OrigHTTPError('Статус страницы не равен 200')
        return homework_statuses.json()


def check_response(response):
    """Проверить валидность ответа."""
    if not isinstance(response, dict):
        raise TypeError('Ошибка в типе ответа API')
    if 'homeworks' not in response:
        raise exceptions.EmptyAnswerAPI('Ошибка доступа по '
                                        'ключу homeworks.')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Homeworks не в виде списка')
    return homeworks


def parse_status(homework):
    """Получить статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Ошибка получения токенов')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    current_report = {}
    prev_report = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_data', current_timestamp)
            new_homeworks = check_response(response)
            if new_homeworks:
                homework = new_homeworks[0]
                current_report['name'] = homework.get('homework_name')
                current_report['output'] = parse_status(homework)
            else:
                current_report['output'] = 'Новые статусы отсутвуют.'
            if current_report != prev_report:
                message = current_report['output']
                send_message(bot, message)
                prev_report = current_report.copy()
            else:
                logging.debug('Статус не поменялся')
        except exceptions.EmptyAnswerAPI as error:
            logging.error(f'Сбой в работе программы: {error}')
        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
            current_report['output'] = error
            if current_report != prev_report:
                send_message(bot, message)
                prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format=('%(asctime)s'
                '%(name)s'
                '%(levelname)s'
                '%(message)s'
                '%(funcName)s'
                '%(lineno)d'),
        level=logging.INFO,
        filename="program.log",
        filemode="w")
    main()
