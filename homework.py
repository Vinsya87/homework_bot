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


HOMEWORK_VERDICTS = {
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
        return True


def get_api_answer(current_timestamp):
    """Запрос к единственному эндпоинту API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        raise Exception(f'Вид ошибки: {error}')
    if homework_statuses.status_code != HTTPStatus.OK.value:
        logger.critical(
            f'Вид ошибки: {ENDPOINT} недоступен. '
            f'Ответ: {homework_statuses.status_code}')
        raise Exception('Нет доступа к API')
    if not homework_statuses:
        raise Exception('Ответ API пустой')
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
    """Извлекает из информации о конкретной домашней работе."""
    key_error = 'Ключ не найден'
    noname_error = 'Неизвестная ошибка:'
    status_msg = 'Статус задания  не задан'
    try:
        homework_name = homework['homework_name']
    except KeyError:
        logger.error(f'{key_error}')
        raise KeyError(f'{key_error}')
    except Exception as error:
        logger.error(f'{noname_error} {error}')
        raise Exception(f'{noname_error} {error}')
    try:
        homework_status = homework['status']
    except KeyError:
        logger.error(f'Ключ {homework_status} не найден')
        raise KeyError(f'Ключ {homework_status} не найден')
    except Exception as error:
        logger.error(f'{noname_error} {error}')
        raise Exception(f'{noname_error} {error}')
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error(f'{status_msg}')
        raise Exception(f'{status_msg}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return (
        f'Изменился статус проверки работы '
        f'"{homework_name}". {verdict}')


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
    current_timestamp = 1644483636
    msg_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            # Если homeworks пуст, ничего не шлем никуда
            if not homeworks:
                continue
            verdict = parse_status(homeworks[0])
            send_message(bot, verdict)
        except Exception as error:
            error = f'Сбой в работе программы: {error}'
            if error != msg_error:
                send_message(bot, msg_error)
                logger.debug(f'Ошибка: {error}', exc_info=True)
                if send_message in True:
                    msg_error = error
        else:
            current_timestamp = response['current_date']
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
