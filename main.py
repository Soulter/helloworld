from astrbot.api import Plugin, Message, on_message
import requests

# 你的 API 地址（无需手动加 /）
BASE_URL = "http://172.16.0.101:32031/order/queue/status/"

# 状态码映射（你可以改成自己的名称）
STATUS_MAP = {
    "0": "待处理",
    "1": "处理中",
    "2": "已完成",
    "3": "已取消",
}

class OrderQuery(Plugin):
    # 匹配：排单 + 空格 + 数字
    @on_message(r"排单\s*\d+")
    async def query_order(self, message: Message):
        text = message.text.strip()

        # 解析命令，比如排单 0
        try:
            status = text.split()[1]
        except:
            return await message.reply("格式错误，应使用：排单 0/1/2/3")

        # 检查状态是否合法
        if status not in STATUS_MAP:
            return await message.reply("状态只能是 0/1/2/3")

        url = BASE_URL + status

        try:
            # 请求接口
            resp = requests.get(url, timeout=5)
            data = resp.json()
        except Exception as e:
            return await message.reply(f"接口请求失败：{e}")

        # 接口返回错误
        if data.get("code") != 0:
            return await message.reply(f"接口错误：{data.get('msg')}")

        orders = data.get("data", [])

        # 无数据时
        if not orders:
            return await message.reply("未查询到排单数据")

        # 取第一条
        o = orders[0]

        username = o.get("username", "未知")
        orderNo = o.get("orderNo", "未知")
        create_time = o.get("orderCreateTime", "未知")
        status_text = STATUS_MAP.get(str(o.get("status")), "未知状态")

        # 格式化输出
        msg = (
            f"📦 排单信息：\n"
            f"👤 用户：{username}\n"
            f"🔢 订单号：{orderNo}\n"
            f"⏰ 创建时间：{create_time}\n"
            f"📘 状态：{status_text}"
        )

        return await message.reply(msg)
