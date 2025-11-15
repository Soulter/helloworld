import io
import requests
from PIL import Image, ImageDraw, ImageFont

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Star, Context, register
from astrbot.api import logger


API_URL = "你的 API 地址，例如 http://example.com/order/list"


def render_order_card(data: list):
    """使用 Pillow 渲染排单卡片"""

    count = len(data)

    # 基础尺寸
    width = 900
    header_height = 120
    row_height = 150
    height = header_height + row_height * max(count, 1)

    # 白底画布
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # 字体（AstrBot 容器一般有 DejaVu 字体）
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
    font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38)

    # 标题
    draw.text((40, 40), f"📋 排单统计：{count} 人", fill="black", font=font_title)

    # 内容区起点
    y = header_height

    if count == 0:
        draw.text((40, y + 20), "暂无排单数据", fill="gray", font=font_text)
    else:
        for item in data:
            draw.text((40, y), f"👤 用户：{item['username']}", fill="black", font=font_text)
            draw.text((40, y + 45), f"📦 订单号：{item['orderNo']}", fill="black", font=font_text)
            draw.text((40, y + 90), f"⏱ 下单时间：{item['orderCreateTime']}", fill="black", font=font_text)
            y += row_height

    # 保存到字节流
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


@register("zyfurry_bot", "jiatao", "排单查询 + 图片渲染插件（Pillow版）", "1.0.0")
class OrderPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("order")
    async def order_cmd(self, event: AstrMessageEvent):
        """查询排单并以图片形式输出"""

        logger.info("开始请求接口获取排单信息…")

        try:
            resp = requests.get(API_URL, timeout=5)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"接口请求失败: {e}")
            yield event.plain_result("❌ 接口请求失败，请稍后再试")
            return

        # 解析 JSON
        try:
            json_data = resp.json()
        except Exception as e:
            logger.error(f"解析 JSON 失败: {e}")
            yield event.plain_result("❌ 数据格式错误")
            return

        if json_data.get("code") != 0:
            yield event.plain_result("❌ 接口返回异常")
            return

        data_list = json_data.get("data", [])

        # 生成图片
        img_bytes = render_order_card(data_list)

        # 由 AstrBot 发送图片
        yield event.image_result(img_bytes)

    async def terminate(self):
        logger.info("插件已卸载")
