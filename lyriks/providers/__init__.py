from .genie import Genie
from .provider import Provider, ProviderFactory
from .qqm import QQMusic
from .vibe import Vibe

# Ensure all providers are registered when importing the providers package
__all__ = [
    'Provider',
    'ProviderFactory',
    'Genie',
    'QQMusic',
    'Vibe',
]
