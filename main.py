from astrbot import AstrBot
import requests

bot = AstrBot.get_bot()

BASE_URL = "http://172.16.0.101:32031/order/queue/status/"

STATUS_MAP = {
    "0": "待处理",
    "1": "处理中",
    "2": "已完成",
    "3": "已取消",
}

@bot.on_message("group", r"排单\s*\d+")
@bot.on_message("private", r"排单\s*\d+")
async def query_order(ctx):
    text = ctx.message_str.strip()

    try:
        status = text.split()[1]
    except:
        return await ctx.reply("格式错误，应使用：排单 0/1/2/3")

    if status not in STATUS_MAP:
        return await ctx.reply("状态只能是 0/1/2/3")

    url = BASE_URL + status

    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
    except Exception as e:
        return await ctx.reply(f"接口请求失败：{e}")

    if data.get("code") != 0:
        return await ctx.reply(f"接口返回错误：{data.get('msg')}")

    orders = data.get("data", [])

    if not orders:
        return await ctx.reply("未查询到排单数据")

    o = orders[0]

    username = o.get("username", "未知")
    orderNo = o.get("orderNo", "未知")
    create_time = o.get("orderCreateTime", "未知")
    status_text = STATUS_MAP.get(str(o.get("status")), "未知状态")

    reply = (
        f"📦 排单信息\n"
        f"👤 用户：{username}\n"
        f"🔢 订单号：{orderNo}\n"
        f"⏰ 创建时间：{create_time}\n"
        f"📘 状态：{status_text}"
    )

    await ctx.reply(reply)
