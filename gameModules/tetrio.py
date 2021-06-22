# I'm thinking this could check for jstris or other games progress... yet no now
import asyncio
import aiohttp
from gameModules.BaseModule import BaseModule
from model.player import TetrioPlayer
from bd import PyDB
from pprint import pprint
from discord import Embed
from datetime import datetime
import math
import os

class TetrioRankModule(BaseModule):
    def __init__(self):
        super().__init__()
        if os.getenv("DEV"):
            self.api = "http://127.0.0.1:5000/"

    api = "https://ch.tetr.io/api/"
    rankColors = {
        "x": 0xff42ba, "u":0xff540a, "ss":0xFFB634, 
        "s+": 0xFFC866,"s": 0xE7B357,"s-": 0xDBA443,
        "a+": 0x44D813,"a": 0x63D33D,"a-": 0x82C66B,
        "b+": 0x5498D8,"b": 0x2978C2,"b-": 0x2365A4,
        "c+": 0x6430D2,"c": 0x593A9A,"c-": 0x67548F,
        "d+": 0x8B78B5,"d": 0x998BB7,"z": 0xA6A6A6

    }

    async def getPlayerProfile(self, username:str):
        return await self._BaseModule__getJson(self.api + f"users/{username}")

    async def getPlayerRecords(self, username:str):
        return await self._BaseModule__getJson(self.api + f"users/{username}/records")

    async def getPlayerNews(self, id:str):
        return await self._BaseModule__getJson(self.api + f"news/user_{id}")
            

    async def updatePlayer(self, pl:TetrioPlayer, db:PyDB):
        
        newsCode, newNews = await self._BaseModule__getJson(self.api + f"news/user_{str(pl._id)}")
        recCode, newRecords = await self._BaseModule__getJson(self.api + f"users/{str(pl._id)}/records")
        infoCode, newInfo = await self._BaseModule__getJson(self.api + f"users/{str(pl._id)}")

        if not all(map(lambda x: x==200, [newsCode, recCode, infoCode])):
            raise Exception("Error fetching data")
        if not all(map(lambda x: x.get("success", True), [newNews, newRecords, newInfo])):
            raise Exception("Error with API")
        
        playerCol = db.db.get_collection(pl.collection)
        res = playerCol.update_one(
            {"_id":pl._id},
            {"$set":{
                "info":newInfo["data"]["user"],
                "records":newRecords["data"]["records"],
                "latestNew": newNews["data"]["news"][0]["_id"]
            }}
        )
        newPlayer = playerCol.find_one({"_id":pl._id})
        return TetrioPlayer.fromDict(newPlayer)

    def getRankUpEmbedFor(self, pl:TetrioPlayer,data:dict):
        embed=Embed(url=f"https://ch.tetr.io/u/{pl.info.username}",
            timestamp=datetime.fromisoformat(data["ts"][:-1]), 
            color=self.rankColors[pl.info.league.rank])
        embed.set_author(name=f"{pl.info.username.upper()} HAS RANKED UP!!", url=f"https://ch.tetr.io/u/{pl.info.username}", icon_url=f"https://tetr.io/res/league-ranks/{pl.info.league.rank}.png")
        embed.set_thumbnail(url=f"https://tetr.io/user-content/avatars/{pl._id}.jpg?rv={pl.info.avatar_revision}")
        embed.add_field(name="Current TR", value=f"{round(pl.info.league.rating)}", inline=True)
        # embed.add_field(name="Current APM", value=f"{pl.info.league.apm}", inline=True)
        # embed.add_field(name="Current PPS", value=f"{pl.info.league.pps}", inline=True)
        # embed.add_field(name="Current VS", value=f"{pl.info.league.vs}", inline=True)
        embed.set_footer(text="Tetra Rank Bot")
        return embed

    async def getNewPersonalBestFor(self, pl: TetrioPlayer, oldPl:TetrioPlayer, data:dict):
        mode = data['data']["gametype"].upper()
        cod,record = await self.getPlayerRecords(pl.info.username)
        newDate = datetime.fromisoformat(data["ts"][:-1])
        embed = Embed(colour=0x6eae18, url=f"https://ch.tetr.io/u/{pl.info.username}", 
            timestamp= datetime.fromisoformat(data["ts"][:-1]))
        embed.set_thumbnail(url=f"https://tetr.io/user-content/avatars/{pl.info._id}.jpg?rv={pl.info.avatar_revision}")
        oldDate = None
        if mode == "40L":
            if oldPl.records.sprintTimeStamp:
                oldDate = datetime.fromisoformat(oldPl.records.sprintTimeStamp[:-1])
            record = record["data"]["records"]["40l"]
            self._fillEmbedPBSprint(pl, oldPl, record, embed)
        if mode == "BLITZ":
            if oldPl.records.blitzTimeStamp:
                oldDate = datetime.fromisoformat(oldPl.records.blitzTimeStamp[:-1])
            record = record["data"]["records"]["blitz"]
            self._fillEmbedPBBlitz(pl, oldPl, record, embed)
        embed.set_author(
            name=f"{pl.info.username.upper()} GOT A NEW {mode} RECORD!!", 
            url=f"https://tetr.io/#r:{record['record']['replayid']}", 
            icon_url="https://tetr.io/res/badges/improvement-local.png")
        
        lastRecordStr = "This is their first ever record."
        if oldDate:
            lastRecordStr = f"The last record was set {(newDate - oldDate).days} days ago."

        embed.description = f"{lastRecordStr} These are the statistics of the new record:"
        embed.set_footer(text="Tetra Rank Bot")
        return embed

    def _fillEmbedPBSprint(self, pl: TetrioPlayer, oldPl:TetrioPlayer, record:dict, embed: Embed):
        oldRecord = oldPl.records.sprint
        finaltime = round(record['record']['endcontext']['finalTime']/1000, 3)
        if oldRecord["record"]:
            oldFinalTime = round(oldRecord['record']['endcontext']['finalTime']/1000, 3)
        else:
            oldFinalTime = math.inf
        # pieces = record['record']['endcontext']['piecesplaced']
        # inputs = record['record']['endcontext']['inputs']
        # finesse = record['record']['endcontext']['finesse']
        # finesse = round((finesse['perfectpieces'] / finesse["faults"])*100, 2)
        # kpp = round(inputs / pieces, 2)
        # pps = round(pieces / finaltime, 2)
        # kps = round(inputs / finaltime, 2)
        # oldPieces = oldRecord['record']['endcontext']['piecesplaced']
        # oldInputs = oldRecord['record']['endcontext']['inputs']
        # oldFinesse = oldRecord['record']['endcontext']['finesse']
        # oldFinesse = round((oldFinesse['perfectpieces'] / oldFinesse["faults"])*100, 2)
        # oldKpp = round(oldInputs / oldPieces, 2)
        # oldPps = round(oldPieces / oldFinalTime, 2)
        # oldKps = round(oldInputs / oldFinalTime, 2)
        embed.add_field(name="Final time: ", value=f"\t__**{finaltime} sec**__ ")
        embed.add_field(name="Previous time: ", value=f"\t**{oldFinalTime} sec**".replace("inf","∞"))
        embed.add_field(name="Improvement: ", value=f"\t**{round(oldFinalTime - finaltime,3)} sec**".replace("inf","∞"))
        # embed.add_field(name="pps:", value=f"\t**{pps}** (+0.7)", inline=True)
        # embed.add_field(name="kpp:", value=f"\t**{kpp}** (-0.2)", inline=True)
        # embed.add_field(name="kps:", value=f"\t**{kps}** (+0.5)", inline=True)
        # embed.add_field(name="pieces:", value=f"\t**{pieces}** (-1)", inline=True)
        # embed.add_field(name="finesse:", value=f"\t**{finesse}%** (+0.2%)", inline=True)
    
    def _fillEmbedPBBlitz(self, pl: TetrioPlayer, oldPl:TetrioPlayer, record:dict, embed: Embed):
        oldRecord = oldPl.records.blitz
        finalscore = record['record']['endcontext']['score']
        oldFinalScore = None
        if oldRecord["record"]:
            oldFinalScore = oldRecord['record']['endcontext']['score']
        else:
            oldFinalScore = 0
        embed.add_field(name="Final score: ", value=f"\t__**{finalscore} pts**__ ")
        embed.add_field(name="Previous score: ", value=f"\t**{oldFinalScore} pts**")
        embed.add_field(name="Improvement: ", value=f"\t**{ finalscore - oldFinalScore } pts**")
