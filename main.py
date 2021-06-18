from model.board import Server
from model.player import TetrioPlayer
from gameModules.tetrio import TetrioRankModule
from strings import utilStrs as strs
from bd import PyDB

import discord
from discord.ext import commands
from discord.ext.commands import Bot
from discord import Message, Guild, TextChannel
from dataclasses import asdict
from bson.objectid import ObjectId
import asyncio
import pandas as pd
import datetime
from typing import List

from dotenv import load_dotenv
from pprint import pprint
import os
import traceback

# TODO need to refactor some stuff, I want this thing to actually be mantainable

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(command_prefix=os.getenv("BOT_PREFIX"))
db = PyDB(os.getenv("DB_CONNECTIONSTR"))

@bot.command(
    name='assignChannel',
    aliases=["assignchannel"],
    category="main features",
    help='assignChannel <textChannel> \n......Use this command to tell me where '
        'to report in this server. Only admins can use this command.')
async def getPlayers(ctx:commands.Context, channel:discord.TextChannel):
    author:discord.Member = ctx.author
    if author.guild_permissions.administrator:
        # Save where to answer
        guildID = ctx.guild.id
        channelID = channel.id
        res = db.db.get_collection(Server.collection).update_one(
            {"serverId":guildID}, 
            {
                "$set":{
                    "serverId" : guildID,
                    "reportChannelId" : channelID,
                }
            },
            upsert=True
        )
        await ctx.send(f"From now on, I'll report on the channel {channel.mention}")
    else:
        await ctx.send("Only server administrators can assign me a channel.")

@bot.command(
    name="assignRole",
    aliases=['assignrole'],
    help="assignRole [<roleTag>]\n......Use this command to restric those who can add "
        "players for me to follow. If no roleTag is specified, then anyone can addPlayers"
)
async def assignRole(ctx:commands.Context, role:discord.Role = None):
    author:discord.Member = ctx.author
    g:discord.Guild = ctx.guild
    guildID = ctx.guild.id
    if author.guild_permissions.administrator:
        serverCol = db.db.get_collection(Server.collection)
        server = serverCol.find_one({"serverId":guildID})
        if not server:
            await ctx.send("I need a text channel to report on before getting a role assigned. Use the command as follows and then try this command aggain:")
            await sendHelp(ctx, cmd="assignChannel")
            return
        if role is None:
            serverCol.update_one(
                {"serverId":guildID},
                {"$unset":{"adminRole":""}}
            )
            await ctx.send("Now anyone can add players to the server playerlist.")
        else:
            serverCol.update_one(
                {"serverId":guildID},
                {"$set":{"adminRole":role.id}}
            )
            await ctx.send(f"From now on, only users with the role '{role.name}' can add players to the server playerlist.")            
    else:
        await ctx.send("Only server administrators can assign me a role.")


@assignRole.error
async def addPlayer_Error(ctx, error:commands.CommandError):
    if isinstance(error, commands.RoleNotFound):
        er:commands.RoleNotFound = error
        await ctx.send(
            f"Excuse me... I could find the role '{er.argument}' on the server, perhaps it's an user or something?\n"
        )
    else:
        print(error)
        await ctx.send(strs.ERROR.format("There was an unexpected error."))
        raise error

@bot.command(
    name="addPlayer",
    help='addPlayer <tetr.io username> '
        # '[<discord mention>]'
        '\n......Report activity of this player '
        'in this server. Optionally, you can @somenone to tag them on their activity.',
    aliases=['addplayer']
)
async def addPlayer(ctx:commands.Context, tName:str, member:discord.Member = None):
    # BACKLOG adding jstris functionality would require a refactor of the code, encapsulate current behavour in tetrioModule
    # TODO independtly of if jstris could be added or not, we should add this code to the module

    # check if server in db, if it doesnt one must be assigned
    guild:discord.Guild = ctx.guild
    guildId = guild.id
    dbRes = db.db.get_collection(Server.collection).find_one({"serverId":guildId})
    if not dbRes:
        await ctx.send("I need to get assigned a channel on this server before you can add players. Tell the admins to use the next command:")
        await sendHelp(ctx, cmd="assignChannel")
        return
    
    adminRoleId = dbRes.get("adminRole",None)
    if adminRoleId is not None:
        author:discord.Member = ctx.author
        authorRoles = list(map(lambda x: x.id, author.roles))
        adminRole:discord.Role = guild.get_role(adminRoleId)
        if adminRoleId not in authorRoles:
            await ctx.send(strs.ERROR.format(f"Only people with the role {adminRole.name} can add new players. Please contact someone with that role."))
            return

    # get user and check if it exists
    tName = tName.lower()
    tetrioMod = TetrioRankModule()
    resCode, reqData  = await tetrioMod.getPlayerProfile(tName)
    if resCode != 200:
        await ctx.send(strs.ERROR.format(f"Error {resCode}"))
        await tetrioMod.close()
        return
    if not reqData["success"]:
        await ctx.send(f"⚠ The player '{tName}' doesn't seem to exist in tetr.io :/")
        await tetrioMod.close()
        return
    
    # get records, chacks only to be sure
    resCode, reqRecData  = await tetrioMod.getPlayerRecords(tName)
    if resCode != 200:
        await ctx.send(strs.ERROR.format(f"Error {resCode}"))
        await tetrioMod.close()
        return
    if not reqRecData["success"]:
        await ctx.send(f"⚠ The player '{tName}' doesn't seem to exist in tetr.io :/")
        await tetrioMod.close()
        return

    # TODO add discord tag if necessary
    playerData = reqData["data"]["user"]
    playerRecords = reqRecData["data"]["records"]
    playerDict = {"info":playerData, "records":playerRecords}

    player:TetrioPlayer = TetrioPlayer.fromDict(playerDict)

    # get also latest news, this will save us time while checking players
    resCode, reqNewData  = await tetrioMod.getPlayerNews(player.info._id)
    if resCode != 200:
        await ctx.send(strs.ERROR.format(f"Error {resCode}"))
        await tetrioMod.close()
        return
    if not reqNewData["success"]:
        await ctx.send(f"⚠ The player '{tName}' doesn't seem to exist in tetr.io :/")
        await tetrioMod.close()
        return

    # all api querys done, close client
    await tetrioMod.close()

    playersCollection = db.db.get_collection(TetrioPlayer.collection)
    dbPlayer = playersCollection.find_one(ObjectId(player.info._id))

    # check if player already in db
    if dbPlayer is None:
        #if player is not in db
        playerDict["_id"] = ObjectId(player.info._id)
        playerDict["guilds"] = [ctx.guild.id]
        playerDict["latestNew"] = reqNewData["data"]["news"][0]["_id"]
        playersCollection.insert_one(playerDict)
    else:
        playersCollection.update_one(
            filter={"_id":ObjectId(player.info._id)},
            update={"$addToSet":{"guilds":ctx.guild.id}}
        )
    
    #in any case need to update guild to include player
    guildsCollection = db.db.get_collection(Server.collection)
    guildsCollection.update_one(
        {"serverId":ctx.guild.id},
        {"$addToSet":{"guildPlayers":player.info._id}}
    )

    await ctx.send(f"The player {tName} was added to the server's player list.")

@addPlayer.error
async def addPlayer_Error(ctx, error:commands.CommandError):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Hmm... Who did you want to add again? Repeat the command as follows ->")
        await sendHelp(ctx,"addPlayer")
    elif isinstance(error, commands.MemberNotFound):
        er:commands.MemberNotFound = error
        await ctx.send(
            f"Excuse me... I could find {er.argument} on the server, perhaps it's a role or something?\n"
            # "I'll try to add the player anyways, you could link them afterwards if I succeed."
        )
    else:
        print(error)
        await ctx.send(strs.ERROR.format("There was an unexpected error."))
        raise error

@bot.command(
    name="showPlayers",
    help='showPlayers\n......Show a list of the players in this server. ',
    aliases=['showplayers']
)
async def showPlayers(ctx:commands.Context):
    guild:discord.Guild = ctx.guild
    serverCol = db.db.get_collection(Server.collection)
    server = serverCol.find_one({"serverId":guild.id})
    if server:
        server = Server.fromDict(server)
        serverPlayers = server.guildPlayers
        playersCol = db.db.get_collection(TetrioPlayer.collection)
        playersCursor = playersCol.find({"info._id":{"$in":serverPlayers}})
        players = await db.getAsList(playersCursor)
        players:List[TetrioPlayer] = list(map(lambda x: TetrioPlayer.fromDict(x), players))
        embed = discord.Embed(
            title=guild.name, 
            colour=discord.Colour(0x8c0000), 
            description="The players in this server are:", 
            timestamp=datetime.datetime.utcnow())
        embed.set_thumbnail(url=guild.icon_url)
        embed.set_footer(text="Tetrio Rank Bot")
        for player in players:
            embed.add_field(
                name=player.info.username.upper(),
                inline=False, 
                value=f"\t.")
        await ctx.send(embed=embed)



bot.remove_command('help')
@bot.command(
    name='help', 
    category="main features",
    help='help [<command>]\n......Display this help message for all commands or just <command> if specified.'
)
async def sendHelp(ctx:commands.Context, cmd:str = None):
    if cmd:
        if cmd in [c.name for c in bot.commands]:
            c:commands.Command = bot.get_command(cmd)
            await ctx.send(strs.DIFF.format(f"+ {c.help}"))
        else:
            cmdstr = "".join([f"+ {c.name}\n" for c in bot.commands])
            await ctx.send(strs.UNEXISTING_COMMAND.format(cmd,cmdstr))
    else:
        cmds = list(filter(lambda s: s.help , bot.commands))
        cmdstr = "".join([f"+ {c.help}\n\n" for c in cmds])
        await ctx.send(strs.DIFF.format(cmdstr))

@bot.command(
    name='dev',
)
async def devCmd(ctx:commands.Context, c:str):
    if ctx.author.id == 146484887413719040:
        exec(c)
        
@bot.command(
    name="testMsg"
)
async def testMsg(ctx:commands.Context):
    embed=discord.Embed(title=" ", description="Current stats:", color=0xff42ba)
    embed.set_author(name="G_RAR has ranked up!!", url="https://ch.tetr.io/u/g_rar", icon_url="https://tetr.io/res/league-ranks/x.png")
    embed.set_thumbnail(url="https://tetr.io/user-content/avatars/5f5be1f6ea3d3a2b3abb9aed.jpg?rv=1601428142396")
    embed.add_field(name="Current APM", value="30", inline=True)
    embed.add_field(name="Current PPS", value="21321", inline=True)
    embed.add_field(name="Current VS", value="341", inline=True)
    embed.add_field(name="Current Glicko", value="341", inline=True)
    embed.set_footer(text="sdfsdfsdf")
    await ctx.send(embed=embed)
    pass




@bot.listen('on_ready')
async def on_ready():
    print("Connected to discord")
    asyncio.ensure_future(lookForTetrioUpdates())


async def lookForTetrioUpdates():
    async def checkPlayer(pl:TetrioPlayer,module:TetrioRankModule):
        resCode, reqNewData  = await module.getPlayerNews(pl._id)
        if resCode != 200:
            print(f"Hubo un error {resCode} al pedir la info del usuario")
            return
        if not reqNewData["success"]:
            print("Hubo un error al pedir la info del usuario")
            return
        latestNew = reqNewData["data"]["news"][0]["_id"]
        if latestNew != pl.latestNew:
            print("Theres new news")
            newData = reqNewData["data"]["news"][0]
            embed = None
            oldPlayer = db.db.get_collection(TetrioPlayer.collection).find_one({"_id":pl._id})
            oldPlayer = TetrioPlayer.fromDict(oldPlayer)
            newPlayer = await module.updatePlayer(pl, db)
            if newData["type"] == "rankup":
                embed = module.getRankUpEmbedFor(newPlayer,newData)
            elif newData["type"] == "personalbest":
                embed = await module.getNewPersonalBestFor(newPlayer, oldPlayer, newData)
            else:
                print("THERE IS NEW TYPE AND IT IS ", newData["type"])

            if embed:
                pprint(str(pl._id))
                # for all servers with this user send embed
                c = db.db.get_collection(Server.collection).find(
                    filter = {"guildPlayers": str(pl._id)},
                    projection = {"reportChannelId": 1}
                )
                servers = await db.getAsList(c)
                for server in servers:
                    ch:TextChannel = bot.get_channel(server["reportChannelId"])
                    if ch is not None:
                        await ch.send(embed = embed)
                    else:
                        print("Can't access chat", server["reportChannelId"], "in server", server["serverId"])
        else:
            print("Nada")

    while True:
        try:
            mod = TetrioRankModule()
            if os.getenv("DEV"):
                a = input("Esperando ordenes...")
                if a == "s":
                    await asyncio.sleep(3*60)
            else:
                await asyncio.sleep(10*60)
            c = db.db.get_collection(TetrioPlayer.collection).find()
            playersDict:list = await db.getAsList(c)
            players:list = list(map(lambda x: TetrioPlayer.fromDict(x), playersDict))
            coros = [checkPlayer(p, mod) for p in players]
            await asyncio.gather(*coros)
            await mod.close()
        except Exception as e:
            traceback.print_exc()
            pass


# TODO need to make the messages and add emotes thingy

if __name__ == '__main__':
    print(bot.command_prefix)
    bot.run(TOKEN)
