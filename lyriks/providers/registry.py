provider_registry = {}


def register_provider(*names: str):
    """
    Decorator to register a provider class with one or more names.
    """

    def wrapper(cls):
        for name in names:
            provider_registry[name] = cls
        return cls

    return wrapper
