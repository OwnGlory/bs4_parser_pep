class ParserFindTagException(Exception):
    """Вызывается, когда парсер не может найти тег."""
    pass


class VersionsNotFoundError(Exception):
    """Вызывается, когда парсер не может найти список с версиями Python."""
    pass


class TypeAndStatusNotFoundError(Exception):
    """Вызывается, когда парсер не может найти тип с статус версии PEP."""
    pass
