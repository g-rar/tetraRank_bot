import aiohttp
import asyncio
import json

class BaseModule:
    def __init__(self):
        self.__client = aiohttp.ClientSession()
        super().__init__()

    async def __getJson(self, url):
        async with self.__client.get(url) as response:
            data = await response.read()
            return (response.status, json.loads(data.decode('utf-8')))

    async def close(self):
        await self.__client.close()