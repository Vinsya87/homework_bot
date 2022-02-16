import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
    except telegram.TelegramError:
        logger.error(f'Не удалось отправить сообщение "{message}"')
    else:
        logger.info(f'Бот отправил сообщение "{message}"')


def get_api_answer(current_timestamp):
    """Запрос к единственному эндпоинту API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        logger.critical(f'Вид ошибки: {error}')
    else:
        if homework_statuses.status_code != HTTPStatus.OK.value:
            logger.critical(
                f'Вид ошибки: {ENDPOINT} недоступен. '
                f'Ответ: {homework_statuses.status_code}')
            raise Exception('Нет доступа к API')
        return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        raise KeyError(f'{error} не верный ответ API')
    if not homeworks:
        logger.debug('Статус проверки не изменился')
    if not isinstance(homeworks, list):
        logger.error('Неверный список работ.')
        raise TypeError('Неверный список работ.')
    return homeworks


def parse_status(homework):
    """Изменения информации о проверке работы."""
    homework_name = homework['homework_name']
    # хотел сделать так homework_name = homework[0]['homework_name']
    # но pytest ругается, по мне так логично :)
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        logger.error(
            f'Статус {homework_status} '
            f'задания "{homework_name}" не задан')
        raise KeyError(
            f'Статус {homework_status} '
            f'задания "{homework_name}" не задан')
    verdict = HOMEWORK_STATUSES[homework_status]
    if homework_status in HOMEWORK_STATUSES:
        return (
            f'Изменился статус проверки работы '
            f'"{homework_name}". {verdict}')
    raise Exception(
        f'Статус {homework_status} '
        f'задания "{homework_name}" не задан')


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for token, token_val in tokens.items():
        if token_val is None:
            logger.critical(
                f'Отсутсвует переменная {token}')
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            verdict = parse_status(homeworks)
            # Если homeworks пуст, ничего не шлем никуда
            if verdict != []:
                homework_status = homeworks[0]['status']
                send_message(bot, verdict)
                # Останавливаю работу бота если задание проверили
                for key in HOMEWORK_STATUSES:
                    if homework_status in key:
                        time.sleep(5)
                        send_message(bot, 'я стоп')
                        sys.exit()
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        else:
            current_timestamp = response['current_date']
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
