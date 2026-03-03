
import discord
from discord.ext import tasks, commands
import os
from dotenv import load_dotenv
from datetime import datetime as dt
import datetime
import zoneinfo
import requests
from dateutil import parser
import logging
from bs4 import BeautifulSoup, Comment
import re
import json

logger = logging.getLogger(__name__)
logging.basicConfig(filename="main.log", level=logging.INFO)

eastern = zoneinfo.ZoneInfo("America/New_York")

load_dotenv()
TOKEN=os.getenv("TOKEN")
WEATHER_CHANNEL=os.getenv("WEATHER_CHANNEL")
DINNER_CHANNEL=os.getenv("DINNER_CHANNEL")
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

weather_c = None # channel to send things in (not initialized now)
dinner_c = None


def get_weather_info(c: tuple[float, float]) -> list:
    r=requests.get(f"https://api.weather.gov/points/{c[0]},{c[1]}")
    p=requests.get(r.json()["properties"]["forecastHourly"]).json()["properties"]["periods"]
    td=dt.now(parser.parse(p[0]["startTime"]).tzinfo).date()
    l=[i for i in p if parser.parse(i["startTime"]).date()==td] # filter returns for info on the current day
    return [[parser.parse(i["startTime"]).hour, i["temperature"], int(i["windSpeed"][:-4]), i["probabilityOfPrecipitation"]["value"], i["shortForecast"]] for i in l]
    #                                                           strip trailing " mph" ^^^                               text description of weather ^^^

sti={"sunny":"☀️", "cloud":"☁️", "fog":"🌫️"}
pti={"rain":"🌧️", "shower":"🌧️", "snow":"❄️", "storm":"⛈️"}

def weather_report(c: tuple[float, float]) -> str:
    ws = get_weather_info(c)
    wo = []
    low_temp = 1000000
    high_temp = -1000000
    high_wind = 0
    for i in ws:
        i[1]=round((i[1]-32)*5/9) # F -> C
        i[2]=round(i[2]*1.609344) # mph -> kph
        i[4]=i[4].lower() # lowercase

        low_temp = min(low_temp, i[1])
        high_temp = max(high_temp, i[1])
        high_wind = max(high_wind, i[2])

        em=[sti[j] for j in sti if j in i[4]] # lists of emojis to add
        sm=[pti[j] for j in pti if j in i[4]]

        sf=f" {i[3]}%" if len(sm) else "" # if there's some kind of precipitation, add the percent chance


        wo.append(f"{str(i[0]).rjust(2)}|{str(i[1]).rjust(3)}C|{str(i[2]).rjust(2)} kph|{''.join(em+sm)}{sf}")

        if (i[1]<=-5): # -5C
            wo.append("🚨🚨WEEWOO🚨🚨 COLD")
        if (i[2]>=15): # 15kph
            wo.append("🚨🚨WEEWOO🚨🚨 WIMDY")
        if (len(sm)): # precipitation
            wo.append("🚨🚨WEEWOO🚨🚨 PISS")

    if low_temp == 1000000:
        low_temp = '-'
    else:
        low_temp = str(low_temp)

    if high_temp == -1000000:
        high_temp = '-'
    else:
        high_temp = str(high_temp)

    high_wind = str(high_wind)

    summary=[]
    summary.append(f" LOW TEMP: { low_temp.rjust(3)}C")
    summary.append(f"HIGH TEMP: {high_temp.rjust(3)}C")
    summary.append(f"HIGH WIMD: {high_wind.rjust(2)} kph")
    summary.append("")

    return '\n'.join(summary + wo)

def extract_items(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.extract()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    for tag in soup.find_all(style=True):
        if any(h in tag["style"].lower() for h in ["display:none", "visibility:hidden"]):
            tag.extract()

    parts = re.split(r' {2,}', re.sub(r'(\\t|\\n)', '', soup.get_text(separator=" ", strip=True)))
    parts = parts[parts.index("Dinner Specials"):]
    match = [i for i,x in enumerate(parts) if re.fullmatch("FOOD ALLERGEN WARNING.*|late night|Late Night", x)]
    parts = parts[:match[0]]
    parts = [i for i in parts if not re.fullmatch(r"\d+.*", i) and "nutrition" not in i]

    last_category = None
    cat = dict()
    for i in parts:
        if (i.lower() == i and i.count(' ') < 4):
            last_category = i
            if (i not in cat):
                cat[i] = []
        elif (last_category is not None):
            cat[last_category].append(i)
    
    return cat

dinner_link = "https://mit.cafebonappetit.com/cafe/"
dinner_sites = ["the-howard-dining-hall-at-maseeh", "new-vassar" , "baker", "simmons", "next", "mccormick"]
dinner_abbr = ["mM", "vV", "bB", "sS", "nN", "cC"]
hide_categories = ["grill", "salad", "condiment", "beverage", "topping", "action", "coffee", "tea", "sushi"]
hide_weekday_categories = ["dessert", "cream"]
dinner_dir = "dinner/"
def dinner_report() -> dict:
    ret = dict()
    for st in dinner_sites:
        r = requests.get(dinner_link + st)
        items = extract_items(str(r.content))
        skipped_categories = []
        real_s = dict()
        for i in items:
            u = True
            for j in hide_categories + hide_weekday_categories:
                if j in i:
                    u = False
            if (u):
                real_s[i] = items[i]
            else:
                skipped_categories.append(i)
        ls = ["skipped categories: " + ", ".join(skipped_categories)]
        for i in real_s:
            ls.append(i + '\n' + ", ".join(real_s[i]))
        ret[st] = '\n'.join(ls)
    return ret
    

@bot.event
async def on_message(message:discord.Message):
    msg = message.content
    if msg=="!meow" and message.author!=bot.user:
        await message.channel.send("meow")
    if message.channel == dinner_c:
        choice = None
        for i in range(6):
            if msg in dinner_abbr[i]:
                choice = dinner_sites[i]
                break
        if (choice is not None):
            await message.channel.send("logged today's choice as " + dinner_sites[i])
            td = dt.date(dt.now()).isoformat()
            d = None
            with open(dinner_dir + td, 'r') as fp:
                d = json.loads(fp.read())
            d["choice"] = choice
            with open(dinner_dir + td, 'w') as fp:
                json.dump(d, fp)
            logger.info(f"logged choice as {choice}, at time {dt.now()}")

@tasks.loop(time=datetime.time(hour=7, minute=0, tzinfo=eastern))
async def morning():
    # weather at 7 am each morning
    logger.info(f"weather report at {dt.now()}")

    woo=weather_report(SAUEL_COORDS)
    await weather_c.send(f"<@{SAUEL}>```"+woo+"```")

    woo=weather_report(ROOWEE_COORDS)
    await weather_c.send(f"<@{ROOWEE}>```"+woo+"```")

@tasks.loop(time=datetime.time(hour=17, minute=0, tzinfo=eastern))
async def dinner():
    logger.info(f"dinner report at {dt.now()}")
    d = dinner_report()
    await dinner_c.send(f"<@{SAUEL}> DINNAUR")
    for i in d:
        await dinner_c.send(i+'\n'+d[i])
    td = dt.date(dt.now()).isoformat()

    with open(dinner_dir + td, 'w') as fp:
        json.dump(d, fp)

@bot.event
async def on_ready():
    global weather_c
    global dinner_c
    logger.info(f"{bot.user} starting {dt.now()}")
    morning.start()
    dinner.start()
    weather_c = await bot.fetch_channel(WEATHER_CHANNEL)
    dinner_c = await bot.fetch_channel(DINNER_CHANNEL)
    logger.info(f"{bot.user} tasks complete {dt.now()}")
    
if __name__ == "__main__":
    bot.run(TOKEN)