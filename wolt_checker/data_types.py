import enum
import typing
from dataclasses import dataclass


class ChatState(enum.Enum):
    START = "start"
    VENUE_SELECTION = "venue_selection"


@dataclass
class ChatInfo:
    state: str
    venues: typing.Optional[typing.List[typing.Dict]] = None
    page_num: int = 0
