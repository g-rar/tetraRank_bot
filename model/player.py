from dataclasses import dataclass, asdict, fields, field
from model.baseModel import BaseModel

@dataclass
class TetrioLeague(BaseModel):
    rank:str
    prev_rank:str
    next_rank:str
    apm:float
    pps:float
    vs:float
    rating:float

    @staticmethod
    def fromDict(d):
        return BaseModel.fromDict(d, TetrioLeague)

@dataclass
class TetrioPlayerRecords(BaseModel):
    sprint:dict
    blitz:dict
    sprintTime:float = None
    sprintID:str = None
    sprintReplayID:str = None
    sprintTimeStamp:str = None
    blitzScore:int = None
    blitzID:str = None
    blitzReplayID:str = None
    blitzTimeStamp:str = None


    @staticmethod
    def fromDict(d):
        spr = d.get("40l", None)
        bltz = d.get("blitz",None)
        ins = TetrioPlayerRecords(spr,bltz)
        if spr:
            ins.sprintID = spr["record"]["_id"]
            ins.sprintReplayID = spr["record"]["replayid"]
            ins.sprintTime = spr["record"]["endcontext"]["finalTime"]
            ins.sprintTimeStamp = spr["record"]["ts"]
        if bltz:
            ins.blitzID = bltz["record"]["_id"]
            ins.blitzReplayID = bltz["record"]["replayid"]
            ins.blitzScore = bltz["record"]["endcontext"]["score"]
            ins.blitzTimeStamp = bltz["record"]["ts"]

        return ins        



@dataclass
class TetrioPlayerInfo(BaseModel):
    _id:str
    username: str
    country: str
    league: TetrioLeague
    avatar_revision:int = None

    @staticmethod
    def fromDict(d):
        return BaseModel.fromDict(d, TetrioPlayerInfo)


@dataclass
class TetrioPlayer(BaseModel):
    _id:str = None
    info:TetrioPlayerInfo = None
    records:TetrioPlayerRecords = None
    guilds: list = field(default_factory=list)
    latestNew:str = None 

    collection:str = "PLAYERS"

    @staticmethod
    def fromDict(d):
        return BaseModel.fromDict(d, TetrioPlayer)



