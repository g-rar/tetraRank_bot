from model.baseModel import BaseModel
from typing import Optional
from dataclasses import dataclass
from dataclasses import field

@dataclass
class Server(BaseModel):
    '''
    A class that represent a server where this bot reports a list of players.
    '''
    serverId: int
    reportChannelId: int
    guildPlayers: list = field(default_factory=list)
    adminRole: Optional[str] = None
    collection: str = "SERVER"

    @staticmethod
    def fromDict(d):
        return BaseModel.fromDict(d, Server)