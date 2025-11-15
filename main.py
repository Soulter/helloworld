from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import requests

# 你的 API 地址
BASE_URL = "http://172.16.0.101:32031/order/queue/status/"

STATUS_MAP = {
    "0": "待处理",
    "1": "处理中",
    "2": "已完成",
    "3": "已取消",
}

@register(
    name="queue_query",
    author="yourname",
    description="排单查询插件",
    version="1.0.0",
    repo="https://example.com"
)
class QueueQueryPlugin(Star):

    def __init__(self, context: Context):
        super().__init__(context)

    # 注册指令
    @filter.command("queue")
    async def query_queue(self, event: AstrMessageEvent):
        """
        根据状态查询排单：
        用法：/queue 0
        """

        msg = event.message_str.strip()  # 用户输入的 原始消息
        logger.info(f"收到排单指令: {msg}")

        parts = msg.split()
        if len(parts) < 2:
            yield event.plain_result("用法错误：/queue 状态\n例如：/queue 0")
            return

        status = parts[1]

        if status not in STATUS_MAP:
            yield event.plain_result("状态只能为：0（待处理），1（处理中），2（已完成），3（已取消）")
            return

        url = BASE_URL + status

        try:
            resp = requests.get(url, timeout=5)
            data = resp.json()
        except Exception as e:
            yield event.plain_result(f"接口请求失败：{e}")
            return

        if data.get("code") != 0:
            yield event.plain_result(f"接口返回错误：{data.get('msg')}")
            return

        orders = data.get("data", [])

        if not orders:
            yield event.plain_result("未查询到排单数据")
            return

        # 目前只输出第一条，如果你要全部我可帮你写循环版本
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

        yield event.plain_result(reply)

    async def terminate(self):
        logger.info("QueueQuery 插件已卸载")
