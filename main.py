import discord
from discord.ext import tasks, commands
import os
from dotenv import load_dotenv
import datetime
import zoneinfo
import requests
from dateutil import parser
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(filename="main.log", level=logging.INFO)

eastern = zoneinfo.ZoneInfo("America/New_York")

load_dotenv()
TOKEN=os.getenv("TOKEN")
CHANNEL=os.getenv("CHANNEL")
NEXT_MEET=os.getenv("NEXT_MEET")
ROOWEE=os.getenv("ROOWEE")
SAUEL=os.getenv("SAUEL")
SAUEL_COORDS=list(map(float,os.getenv("SAUEL_COORDS").split(',')))
ROOWEE_COORDS=list(map(float,os.getenv("ROOWEE_COORDS").split(',')))

intents=discord.Intents.none()
intents.messages=True # run on message received
intents.message_content=True # access content
intents.guilds=True # access server information
bot=commands.Bot(command_prefix='!',intents=intents)

sc=0 # channel to send things in (not initialized now)

def get_weather_info(c: tuple[float, float]) -> list:
    r=requests.get(f"https://api.weather.gov/points/{c[0]},{c[1]}")
    p=requests.get(r.json()["properties"]["forecastHourly"]).json()["properties"]["periods"]
    td=datetime.datetime.now(parser.parse(p[0]["startTime"]).tzinfo).date()
    l=[i for i in p if parser.parse(i["startTime"]).date()==td] # filter returns for info on the current day
    return [[parser.parse(i["startTime"]).hour, i["temperature"], int(i["windSpeed"][:-4]), i["probabilityOfPrecipitation"]["value"], i["shortForecast"]] for i in l]
    #                                                           strip trailing " mph" ^^^                               text description of weather ^^^

sti={"sunny":"☀️", "cloud":"☁️", "fog":"🌫️"}
pti={"rain":"🌧️", "shower":"🌧️", "snow":"❄️", "storm":"⛈️"}

def weather_report(c: tuple[float, float]) -> str:
    ws = get_weather_info(c)
    wo = []
    for i in ws:
        i[1]=round((i[1]-32)*5/9) # F -> C
        i[2]=round(i[2]*1.609344) # mph -> kph
        i[4]=i[4].lower() # lowercase

        em=[sti[j] for j in sti if j in i[4]] # lists of emojis to add
        sm=[pti[j] for j in pti if j in i[4]]

        sf=f"{i[3]}%" if len(sm) else "" # if there's some kind of precipitation, add the percent chance


        wo.append(f"{str(i[0]).rjust(2)}|{str(i[1]).rjust(3)}C|{str(i[2]).rjust(2)} kph|{''.join(em+sm)}{sf}")

        if (i[1]<=-10): # -10C
            wo.append("🚨🚨WEEWOO🚨🚨 COLD")
        if (i[2]>=15): # 15kph
            wo.append("🚨🚨WEEWOO🚨🚨 WIMDY")
        if (len(sm)): # precipitation
            wo.append("🚨🚨WEEWOO🚨🚨 PISS")

    return '\n'.join(wo)



@bot.event
async def on_message(message:discord.Message):
    if message.content=="!meow" and message.author!=bot.user:
        await message.channel.send("meow")

@tasks.loop(time=datetime.time(hour=8, minute=0, tzinfo=eastern))
async def morning():
    # weather at 8 am each morning
    logger.info(f"weather report at {datetime.datetime.now()}")

    woo=weather_report(SAUEL_COORDS)
    await sc.send(f"<@{SAUEL}>```"+woo+"```")

    woo=weather_report(ROOWEE_COORDS)
    await sc.send(f"<@{ROOWEE}>```"+woo+"```")

@bot.event
async def on_ready():
    global sc
    logger.info(f"{bot.user} starting {datetime.datetime.now()}")
    morning.start()
    sc = await bot.fetch_channel(CHANNEL)
    logger.info(f"{bot.user} tasks complete {datetime.datetime.now()}")
    
bot.run(TOKEN)