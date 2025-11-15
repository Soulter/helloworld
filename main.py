from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import requests
import html
from html2image import Html2Image
import uuid
import os

BASE_URL = "http://172.16.0.101:32031/order/queue/status/"

STATUS_MAP = {
    "0": "待处理",
    "1": "处理中",
    "2": "已完成",
    "3": "已取消",
}


@register("zyfurry_bot", "zyfurry", "排单图文插件（精致白底卡片）", "2.2.0", "https://example.com")
class ZyFurryBot(Star):

    def __init__(self, context: Context):
        super().__init__(context)
        self.hti = Html2Image(output_path="/tmp")

    @filter.command("queueimg")
    async def query_queue_img(self, event: AstrMessageEvent):
        """
        /queueimg 0   → 查询排单 → 白底卡片图片返回
        """

        args = event.message_str.split()
        if len(args) < 2:
            yield event.plain_result("用法：/queueimg <状态>\n例：/queueimg 0")
            return

        status = args[1]
        if status not in STATUS_MAP:
            yield event.plain_result("状态必须为 0/1/2/3")
            return

        # API 请求
        try:
            resp = requests.get(BASE_URL + status, timeout=6)
            js = resp.json()
        except Exception as e:
            yield event.plain_result(f"接口异常：{e}")
            return

        orders = js.get("data", [])
        total = len(orders)

        # HTML 生成
        items_html = ""
        for o in orders:
            username = html.escape(o.get("username", "未知"))
            order_no = html.escape(o.get("orderNo", "未知"))
            order_time = html.escape(o.get("orderCreateTime", "未知"))
            status_text = STATUS_MAP.get(str(o["status"]), "未知")

            items_html += f"""
                <div class="item">
                    <div class="title">👤 {username}</div>
                    <div class="line">🧾 订单号：<span class="code">{order_no}</span></div>
                    <div class="line">📌 状态：<b>{status_text}</b></div>
                    <div class="line">⏱ 下单时间：{order_time}</div>
                </div>
                <div class="divider"></div>
            """

        # HTML 模板（白底、现代、专业）
        html_code = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: "Microsoft YaHei", sans-serif;
                    background: #fafafa;
                    margin: 0;
                    padding: 30px;
                }}
                .card {{
                    background: #ffffff;
                    width: 650px;
                    margin: auto;
                    padding: 30px 40px;
                    border-radius: 12px;
                    box-shadow: 0px 4px 16px rgba(0,0,0,0.08);
                }}
                .header {{
                    font-size: 26px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .subinfo {{
                    font-size: 16px;
                    color: #666;
                    margin-bottom: 25px;
                }}
                .item {{
                    margin-bottom: 15px;
                }}
                .title {{
                    font-size: 20px;
                    font-weight: 600;
                    margin-bottom: 6px;
                }}
                .line {{
                    margin: 4px 0;
                    font-size: 16px;
                }}
                .code {{
                    font-family: Consolas, monospace;
                    background: #f2f2f2;
                    padding: 2px 5px;
                    border-radius: 4px;
                }}
                .divider {{
                    height: 1px;
                    background: #eaeaea;
                    margin: 16px 0;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="header">📋 排单统计结果</div>
                <div class="subinfo">
                    状态：{STATUS_MAP[status]}（{status}）<br>
                    记录总数：{total}
                </div>

                {items_html}

            </div>
        </body>
        </html>
        """

        # 生成图片
        file_name = f"queue_{uuid.uuid4().hex}.png"
        file_path = f"/tmp/{file_name}"

        self.hti.screenshot(
            html_str=html_code,
            save_as=file_name,
            size=(700, 10)
        )

        # 返回图片
        yield event.image_result(file_path)

    async def terminate(self):
        logger.info("排单图文插件已卸载")
