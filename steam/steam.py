import json
import os
from lxml import etree
from asyncio import sleep

from hoshino import service, aiorequests

sv = service.Service("steam", enable_on_default=True)

current_folder = os.path.dirname(__file__)
config_file = os.path.join(current_folder, 'steam.json')
with open(config_file, mode="r") as f:
    f = f.read()
    cfg = json.loads(f)

playing_state = {}
async def format_id(id:str)->str:
    if id.startswith('76561198') and len(id)==17:
        return id
    else:
        resp= await aiorequests.get(f'https://steamcommunity.com/id/{id}?xml=1')
        xml=etree.XML(await resp.content)
        return xml.xpath('/profile/steamID64')[0].text

@sv.on_prefix("添加steam订阅")
async def steam(bot, ev):
    account = str(ev.message).strip()
    try:
        await update_steam_ids(account, ev["group_id"])
        await bot.send(ev, "订阅成功")
    except:
        await bot.send(ev, "订阅失败")


@sv.on_prefix("取消steam订阅")
async def steam(bot, ev):
    account = str(ev.message).strip()
    try:
        await del_steam_ids(account, ev["group_id"])
        await bot.send(ev, "取消订阅成功")
    except:
        await bot.send(ev, "取消订阅失败")


@sv.on_prefix("steam订阅列表")
async def steam(bot, ev):
    group_id = ev["group_id"]
    msg = '======steam======\n'
    await update_game_status()
    for key, val in playing_state.items():
        if group_id in cfg["subscribes"][str(key)]:
            if val["gameextrainfo"] == "":
                msg += "%s 没在玩游戏\n" % val["personaname"]
            else:
                msg += "%s 正在游玩 %s\n" % (val["personaname"], val["gameextrainfo"])
    await bot.send(ev, msg)


@sv.on_prefix("查询steam账号")
async def steam(bot, ev):
    account = str(ev.message).strip()
    rsp = await get_account_status(account)
    if rsp["personaname"] == "":
        await bot.send(ev, "查询失败！")
    elif rsp["gameextrainfo"] == "":
        await bot.send(ev, f"%s 没在玩游戏！" % rsp["personaname"])
    else:
        await bot.send(ev, f"%s 正在玩 %s ！" % (rsp["personaname"], rsp["gameextrainfo"]))


async def get_account_status(id) -> dict:
    id=await format_id(id)
    params = {
        "key": cfg["key"],
        "format": "json",
        "steamids": id
    }
    resp = await aiorequests.get("https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/", params=params)
    rsp = await resp.json()
    friend = rsp["response"]["players"][0]
    return {
        "personaname": friend["personaname"] if "personaname" in friend else "",
        "gameextrainfo": friend["gameextrainfo"] if "gameextrainfo" in friend else ""
    }


async def update_game_status():
    params = {
        "key": cfg["key"],
        "format": "json",
        "steamids": ",".join(cfg["subscribes"].keys())
    }
    resp = await aiorequests.get("https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/", params=params)
    rsp = await resp.json()
    for friend in rsp["response"]["players"]:
        playing_state[friend["steamid"]] = {
            "personaname": friend["personaname"],
            "gameextrainfo": friend["gameextrainfo"] if "gameextrainfo" in friend else ""
        }
    return playing_state


async def update_steam_ids(steam_id, group):
    steam_id=await format_id(steam_id)
    if steam_id not in cfg["subscribes"]:
        cfg["subscribes"][str(steam_id)] = []
    if group not in cfg["subscribes"][str(steam_id)]:
        cfg["subscribes"][str(steam_id)].append(group)
    with open(config_file, mode="w") as fil:
        json.dump(cfg, fil, indent=4, ensure_ascii=False)
    await update_game_status()


async def del_steam_ids(steam_id, group):
    steam_id=await format_id(steam_id)
    if group in cfg["subscribes"][str(steam_id)]:
        cfg["subscribes"][str(steam_id)].remove(group)
    with open(config_file, mode="w") as fil:
        json.dump(cfg, fil, indent=4, ensure_ascii=False)
    await update_game_status()


@sv.scheduled_job('cron', minute='*/2')
async def check_steam_status():
    old_state = playing_state.copy()
    await update_game_status()
    for key, val in playing_state.items():
        if val["gameextrainfo"] != old_state[key]["gameextrainfo"]:
            if val["gameextrainfo"] == "":
                await broadcast(cfg["subscribes"][key],
                                "%s 不玩 %s 了！" % (val["personaname"], old_state[key]["gameextrainfo"]))
            else:
                await broadcast(cfg["subscribes"][key],
                                "%s 正在游玩 %s ！" % (val["personaname"], val["gameextrainfo"]))


async def broadcast(group_list: list, msg):
    for group in group_list:
        await sv.bot.send_group_msg(group_id=group, message=msg)
        await sleep(0.5)
