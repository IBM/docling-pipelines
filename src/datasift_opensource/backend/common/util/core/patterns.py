"""Design pattern implementations."""


class Singleton(type):
    """
    Singleton metaclass implementation.

    Usage:
        class MyClass(metaclass=Singleton):
            pass
    """

    _instances: dict[type, object] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


# Made with Bob
