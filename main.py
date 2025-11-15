from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import requests
import html

# 请根据你的实际地址修改（末尾带 / ）
BASE_URL = "http://172.16.0.101:32031/order/queue/status/"

STATUS_MAP = {
    "0": "待处理",
    "1": "处理中",
    "2": "已完成",
    "3": "已取消",
}

# 为避免一次性输出太多，最多展示前 N 条记录，超出会显示摘要
MAX_DISPLAY = 20

@register(
    "zyfurry_bot",
    "zyfurry",
    "排单查询插件（自动统计人数 & 富文本卡片）",
    "1.0.2",
    "https://example.com"
)
class ZyFurryBot(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("queue")
    async def query_queue(self, event: AstrMessageEvent):
        """
        用法：/queue 0
        根据状态查询并返回自动统计人数的富文本卡片
        """
        text = event.message_str.strip()
        logger.info(f"收到排单指令: {text}")

        parts = text.split()
        if len(parts) < 2:
            yield event.plain_result("用法：/queue <状态>\n例如：/queue 0")
            return

        status = parts[1]
        if status not in STATUS_MAP:
            yield event.plain_result("状态只能是：0（待处理），1（处理中），2（已完成），3（已取消）")
            return

        url = BASE_URL + status
        try:
            resp = requests.get(url, timeout=6)
        except Exception as e:
            yield event.plain_result(f"接口请求失败：{e}")
            return

        # 防止非 JSON 导致崩溃
        try:
            data = resp.json()
        except Exception:
            # 把服务器返回的文本直接回传，便于排查
            body = resp.text
            # 截断过长的 body，防止太多字符
            if len(body) > 1000:
                body = body[:1000] + "...(truncated)"
            yield event.plain_result(f"接口未返回 JSON：\nHTTP {resp.status_code}\n{body}")
            return

        if data.get("code") != 0:
            yield event.plain_result(f"接口错误：{data.get('msg')}")
            return

        orders = data.get("data", []) or []
        total = len(orders)

        # 统计人数（按 username 去重计数） — 如果你要按记录数而不是去重，请改为 total
        usernames = [o.get("username") for o in orders if o.get("username") is not None]
        unique_usernames = set(usernames)
        people_count = len(unique_usernames)

        # 构建富文本卡片（Markdown 风格）
        card_lines = []
        card_lines.append("**📋 排单统计结果**")
        card_lines.append("")
        card_lines.append(f"**查询状态：** {STATUS_MAP.get(status, status)}  （状态码：{status}）")
        card_lines.append(f"**总记录数：** {total}")
        card_lines.append(f"**不同用户数（去重）：** {people_count}")
        card_lines.append("")
        card_lines.append("---")
        card_lines.append("")
        card_lines.append("### 🧾 排单列表")

        if total == 0:
            card_lines.append("")
            card_lines.append("> 未查询到排单数据")
        else:
            # 展示最多 MAX_DISPLAY 条
            display_count = min(total, MAX_DISPLAY)
            for idx, o in enumerate(orders[:display_count], start=1):
                # html.escape / html.unescape 可防止文本里有特殊字符破坏 Markdown
                username = html.escape(str(o.get("username", "未知")))
                orderNo = html.escape(str(o.get("orderNo", "未知")))
                status_text = STATUS_MAP.get(str(o.get("status")), f"状态码:{o.get('status')}")
                create_time = html.escape(str(o.get("orderCreateTime", "未知")))

                card_lines.append(f"#### {idx}. {username}")
                card_lines.append(f"> 🧾 订单号：`{orderNo}`  ")
                card_lines.append(f"> 🔖 状态：**{status_text}**  ")
                card_lines.append(f"> 🕒 下单时间：{create_time}  ")
                card_lines.append("")  # 分隔

            if total > MAX_DISPLAY:
                card_lines.append(f"（仅显示前 {MAX_DISPLAY} 条，共 {total} 条）")
                card_lines.append("如需查看更多，请使用分页或按条件过滤（例如 /queue user 张三）")

        # 最终合并并返回
        final_card = "\n".join(card_lines)
        yield event.plain_result(final_card)

    async def terminate(self):
        logger.info("zyfurry_bot 插件已卸载")
