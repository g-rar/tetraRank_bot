from model.board import Server
from model.player import TetrioPlayer
import pymongo
from pymongo.cursor import Cursor
import os

class PyDB:
    
    def __init__(self, connectionStr):
        super().__init__()
        self.client = pymongo.MongoClient(connectionStr)
        self.db = self.client.get_database("TetraRankBotDB")
        if os.getenv("DEV"):
            self.db = self.client.get_database("TetraRankDevDB")
        
    async def getAsList(self, c:Cursor) -> list:
        ret = [val for val in c]
        return ret
