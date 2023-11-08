class EmptyAnswerAPI(KeyError):
    '''Обработка исключения при пустом ответе от API'''

    pass


class OrigExceptError(Exception):
    '''Обработка исключения ошибки при запросе к API'''

    pass


class OrigHTTPError(Exception):
    '''Обработка исключения при ошибке HTTP'''

    pass
