from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import requests

BASE_URL = "http://172.16.0.101:32031/order/queue/status/"

STATUS_MAP = {
    "0": "待处理",
    "1": "处理中",
    "2": "已完成",
    "3": "已取消",
}

@register(
    "zyfurry_bot",
    "zyfurry",
    "排单查询插件（Star 插件版）",
    "1.0.0",
    "https://example.com"
)
class ZyFurryBot(Star):

    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("queue")
    async def query_queue(self, event: AstrMessageEvent):
        """排单查询：/queue 0"""
        text = event.message_str.strip()
        logger.info(f"收到排单指令: {text}")

        parts = text.split()
        if len(parts) < 2:
            yield event.plain_result("用法：/queue 0")
            return

        status = parts[1]
        if status not in STATUS_MAP:
            yield event.plain_result("状态只能是 0/1/2/3")
            return

        url = BASE_URL + status

        try:
            resp = requests.get(url, timeout=5)
            data = resp.json()
        except Exception as e:
            yield event.plain_result(f"接口请求失败：{e}")
            return

        if data.get("code") != 0:
            yield event.plain_result(f"接口错误：{data.get('msg')}")
            return

        orders = data.get("data", [])
        if not orders:
            yield event.plain_result("未查询到排单数据")
            return

        order = orders[0]

        username = order.get("username", "未知")
        orderNo = order.get("orderNo", "未知")
        create_time = order.get("orderCreateTime", "未知")
        status_text = STATUS_MAP.get(str(order.get("status")), "未知状态")

        result = (
            f"📦 排单信息\n"
            f"👤 用户：{username}\n"
            f"🔢 订单号：{orderNo}\n"
            f"⏰ 创建时间：{create_time}\n"
            f"📘 状态：{status_text}"
        )

        yield event.plain_result(result)

    async def terminate(self):
        logger.info("zyfurry_bot 插件已卸载")
