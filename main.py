from discord.member import Member
from model.board import Server
from model.player import TetrioPlayer
from gameModules.tetrio import TetrioRankModule
from strings import utilStrs as strs
from bd import PyDB
from utils import setupButtonNavigation

import discord
from discord.ext import commands
from discord.ext.commands import Bot
from discord import Message, Guild, TextChannel
from discord_components import DiscordComponents, Button, ButtonStyle, InteractionType


from dataclasses import asdict
from bson.objectid import ObjectId
import asyncio
import pandas as pd
import datetime
from typing import List

from dotenv import load_dotenv
import pprint as pretty_print
from pprint import pprint
import os
import traceback

# TODO need to refactor some stuff, I want this thing to actually be mantainable

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
DEV_ID = os.getenv("DEV_USER_ID")
bot = Bot(command_prefix=os.getenv("BOT_PREFIX"))
DiscordComponents(bot)
db = PyDB(os.getenv("DB_CONNECTIONSTR"))

@bot.command(
    name='assignChannel',
    aliases=["assignchannel"],
    category="main features",
    help='assignChannel <textChannel> \n......Use this command to tell me where '
        'to report in this server. Only admins can use this command.')
async def assignChannel(ctx:commands.Context, channel:discord.TextChannel):
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
    name="addAdminRole",
    aliases=['addadminrole'],
    help="addAdminRole <roleTag>\n......Use this command to restric those who can add "
        "players for me to follow. If there are no admin roles, then anyone can add players "
        "to the server list."
)
async def addAdminRole(ctx:commands.Context, role:discord.Role):
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
        else:
            serverCol.update_one(
                {"serverId":guildID},
                {"$addToSet":{"adminRoles":role.id}}
            )
            await ctx.send(f"From now on, users with the role '{role.name}' can add players to the server playerlist.")            
    else:
        await ctx.send("Only server administrators can assign me a role.")


@addAdminRole.error
async def addAdminRole_Error(ctx, error:commands.CommandError):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("What role did you want to add again? Repeat the command as follows ->")
        await sendHelp(ctx, "addAdminRole")
    elif isinstance(error, commands.RoleNotFound):
        er:commands.RoleNotFound = error
        await ctx.send(
            f"Excuse me... I could find the role '{er.argument}' on the server, perhaps it's an user or something?\n"
        )
    else:
        print(error)
        await ctx.send(strs.ERROR.format("There was an unexpected error."))
        raise error


@bot.command(
    name="removeAdminRole",
    aliases=['removeadminrole'],
    help="removeAdminRole [<roleTag>]\n......Use this command to remove a role who "
        "will no longer be able to add players to the server's list."
)
async def removeAdminRole(ctx:commands.Context, role:discord.Role = None):
    author:discord.Member = ctx.author
    g:discord.Guild = ctx.guild
    guildID = ctx.guild.id
    if author.guild_permissions.administrator:
        serverCol = db.db.get_collection(Server.collection)
        server = serverCol.find_one({"serverId":guildID})
        if not server:
            await ctx.send("I need a text channel to report on before managing roles. Use the command as follows and then try this command aggain:")
            await sendHelp(ctx, cmd="assignChannel")
            return
        else:
            serverCol.update_one(
                {"serverId":guildID},
                {"$pull":{"adminRoles":role.id}}
            )
            await ctx.send(f"From now on, users with the role '{role.name}' will no longer be able to add players to the server playerlist.")            
    else:
        await ctx.send("Only server administrators can remove a role.")


@removeAdminRole.error
async def removeAdminRole_Error(ctx, error:commands.CommandError):
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
        'in this server.', #Optionally, you can @somenone to tag them on their activity.',
    aliases=['addplayer']
)
async def addPlayer(ctx:commands.Context, tName:str, member:discord.Member = None):
    # BACKLOG adding jstris functionality would require a refactor of the code, encapsulate current behavour in tetrioModule
    # TODO independtly of if jstris could be added or not, we should add this code to the module
    # BACKLOG adding support for discord mentions

    # check if server in db, if it doesnt one must be assigned
    guild:discord.Guild = ctx.guild
    guildId = guild.id
    dbRes = db.db.get_collection(Server.collection).find_one({"serverId":guildId})
    if not dbRes:
        await ctx.send("I need to get assigned a channel on this server before you can add players. Tell the admins to use the next command:")
        await sendHelp(ctx, cmd="assignChannel")
        return
    
    adminRoleIds = dbRes.get("adminRoles",[])
    if len(adminRoleIds) != 0:
        author:discord.Member = ctx.author
        authorRoles = list(map(lambda x: x.id, author.roles))
        authorHasRole = any(authorRole in adminRoleIds for authorRole in authorRoles)
        if not authorHasRole:
            await ctx.send(strs.ERROR.format("You do not have any of the roles allowed for adding players. Please contact the server administrator."))
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
        server:Server = Server.fromDict(server)
        playersCol = db.db.get_collection(TetrioPlayer.collection)
        playersCursor = playersCol.find({"guilds":server.serverId}, sort=[("info.username",1)])
        players = await db.getAsList(playersCursor)
        players:List[TetrioPlayer] = list(map(lambda x: TetrioPlayer.fromDict(x), players))
        if len(players) > 20:
            embedList = []
            embedPlayers = []
            page = 1
            while len(players) != 0:
                embedPlayers.append(
                    # ej. ROADTOXRANK
                    players.pop(0).info.username.upper().replace("_","\\_")
                )
                if len(embedPlayers) == 20 or len(players) == 0:
                    playersStr = "\n".join(embedPlayers)
                    embed = discord.Embed(
                        title=f"{guild.name} (Page #{page})\n", 
                        colour=discord.Colour(0x82a35b), 
                        description=f"Showing players from {embedPlayers[0]} to {embedPlayers[-1]}:\n"+playersStr, 
                        timestamp=datetime.datetime.utcnow())
                    embedList.append(embed)
                    embedPlayers = []
                    page += 1
            await setupButtonNavigation(ctx, embedList, bot)
        else:
            playersStr = ""
            for player in players:
                playersStr += player.info.username.upper() + "\n"
            embed = discord.Embed(
                title=guild.name, 
                colour=discord.Colour(0x82a35b), 
                description="The players in this server are:\n"+playersStr, 
                timestamp=datetime.datetime.utcnow())
            embed.set_thumbnail(url=guild.icon_url)
            embed.set_footer(text="Tetrio Rank Bot")
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
    if ctx.author.id == DEV_ID:
        exec(c)


@bot.command(
    name="list_servers"
)
async def listServers(ctx: commands.Context):
    if ctx.author.id != int(DEV_ID):
        return
    c = db.db.get_collection(Server.collection).find()
    serversList:list = await db.getAsList(c)
    servers:List[Server] = list(map(lambda x: Server.fromDict(x), serversList))
    msg = ""
    for server in servers:
        guild:Guild = bot.get_guild(server.serverId)
        # guildOwner:Member = bot.get_user(guild.owner_id)
        # Su dueño es {guildOwner.display_name if guildOwner else 'no tiene'} ({guild.owner_id})
        if not guild:
            continue
        msg += f"""
        El servidor {guild.name} ({guild.id})
        Icono: {guild.icon_url}
        \n_____________________________\n
        """
    await ctx.send(msg)


@bot.listen('on_ready')
async def on_ready():
    print("Connected to discord")
    asyncio.ensure_future(lookForTetrioUpdates())


#TODO when guild not found, send notification and backup, then delete it
#TODO if there are no new news

async def lookForTetrioUpdates():
    async def checkPlayer(pl:TetrioPlayer,module:TetrioRankModule):
        try:
            resCode, reqNewData  = await module.getPlayerNews(pl._id)
            if resCode != 200:
                print(f"Hubo un error {resCode} al pedir la info del usuario")
                return
            if not reqNewData["success"]:
                print("Hubo un error al pedir la info del usuario")
                return
            latestRawNew = reqNewData["data"]["news"][0]
            latestNew = None if not latestRawNew else latestRawNew["_id"]
            if latestNew and latestNew != pl.latestNew:
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
        except Exception as e:
            print("While reading user:" + pl.info.username + ", id: " + pl.info._id)
            traceback.print_exc()
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
        except Exception as e:
            traceback.print_exc()
        finally:
            await mod.close()



# TODO need to make the messages and add emotes thingy

if __name__ == '__main__':
    print(bot.command_prefix)
    bot.run(TOKEN)
