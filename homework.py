import telegram
import time
import requests
import logging
import sys
import os

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
    logger.info(f"Начало отправки сообщения: {message}")
    bot_message = bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    if not bot_message:
        raise telegram.TelegramError('Сообщение не отправлено')
    else:
        logger.info(f'Сообщение отправлено: {message}')


def get_api_answer(timestamp):
    """Получить статус домашней работы из обновления."""
    cur_timestamp = timestamp or int(time.time())
    params = dict(url=ENDPOINT, headers=HEADERS,
                  params={"from_date": cur_timestamp})
    try:
        homework_statuses = requests.get(**params)
    except Exception as error:
        logger.error(f'Ошибка при запросе к API: {error}')
    else:
        if homework_statuses.status_code != HTTPStatus.OK:
            error_message = 'Статус страницы не равен 200'
            raise requests.HTTPError(error_message)
        return homework_statuses.json()


def check_response(response):
    """Проверить валидность ответа."""
    logger.info('Ответ от сервера получен')
    homeworks_response = response['homeworks']
    logger.info('Список домашних работ получен')
    if not homeworks_response:
        error_message = "Отсутствует статус homeworks"
        raise LookupError(error_message)
    if not isinstance(homeworks_response, list):
        error_message = 'Невернй тип входящих данных'
        raise TypeError(error_message)
    if 'homeworks' not in response.keys():
        error_message = 'Ключ "homeworks" отсутствует'
        raise KeyError(error_message)
    if 'current_date' not in response.keys():
        error_message = 'Ключ "current_date" отсутствует в словаре'
        raise KeyError(error_message)
    return homeworks_response


def parse_status(homework):
    """Получить статус домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_VERDICTS[homework_status]
    if not verdict:
        error_message = 'Cтатус отсутвует в словаре'
        raise KeyError(error_message)
    if homework_status not in HOMEWORK_VERDICTS:
        error_message = 'Статус не существует'
        raise KeyError(error_message)
    if "homework_name" not in homework:
        error_message = 'Домашняя работа не существует'
        raise KeyError(error_message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if not check_tokens():
        logger.critical('Ошибка получения токенов')
        sys.exit()
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

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logger.error(message)
        else:
            logger.error("Сбой, ошибка не найдена")
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
        filemode="w",
    )
    main()
