from abc import ABC
from dataclasses import dataclass


@dataclass
class Song(ABC):
    """
    Represents a song in a provider or API-specific context.
    """

    id: int
    album_index: int
    title: str
