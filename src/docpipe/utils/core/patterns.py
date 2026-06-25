"""Design pattern implementations."""

from typing import ClassVar


class Singleton(type):
    """
    Singleton metaclass implementation.

    Usage:
        class MyClass(metaclass=Singleton):
            pass
    """

    _instances: ClassVar[dict[type, object]] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
