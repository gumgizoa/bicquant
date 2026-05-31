from threading import Lock


class MetaSingleton(type):
    _instances = {}
    _lock = Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super(MetaSingleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def inherit_doc(from_func):
    """Decorator to inherit docstring from another function."""

    def decorator(func):
        func.__doc__ = from_func.__doc__
        return func

    return decorator
