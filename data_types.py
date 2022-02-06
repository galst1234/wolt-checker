import enum
import typing
from dataclasses import dataclass


class ChatState(enum.Enum):
    START = 0
    VENUE_SELECTION = 1


@dataclass
class ChatInfo:
    state: ChatState
    venues: typing.Optional[typing.List[typing.Dict]] = None
