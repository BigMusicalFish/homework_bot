import logging
import os
import sys
import time

import exceptions
import telegram
import requests

from http import HTTPStatus
from dotenv import load_dotenv

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
        homework_statuses = requests.get(**params)
    except Exception as error:
        return requests.RequestException(f'Ошибка при запросе к API: {error}')
    else:
        if homework_statuses.status_code != HTTPStatus.OK:
            raise requests.HTTPError('Статус страницы не равен 200')
        return homework_statuses.json()


def check_response(response):
    """Проверить валидность ответа."""
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        return exceptions.EmptyAnswerAPI('Ошибка доступа по '
                                         f'ключу homeworks: {error}')
    if not isinstance(response, dict):
        raise TypeError('Ошибка в типе ответа API')
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
    current_timestamp = int(time.time())
    current_report = {}
    prev_report = {}
    while True:
        try: 
            response = get_api_answer(current_timestamp) 
            homework = check_response(response)[0] 
            if homework: 
                message = parse_status(homework) 
                current_report[ 
                    response.get("homework_name") 
                ] = response.get("status") 
                if current_report != prev_report: 
                    send_message(bot, message) 
                    prev_report = current_report.copy() 
                    current_report[ 
                        response.get("homework_name") 
                    ] = response.get("status") 
            current_timestamp = response.get("current_date")

        except exceptions.EmptyAnswerAPI as error:
            logging.error(f'Сбой в работе программы: {error}')
        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
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
