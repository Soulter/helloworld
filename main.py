import os
import threading
import re
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter
from astrbot.core.message.components import Image, Plain
from astrbot.api.provider import ProviderRequest
from astrbot.api import logger

from .config.config_manager import ConfigManager
from .memes.meme_manager import MemeManager


@register(
    "astrbot_meme_plugin",
    "user",
    "基于archive目录的表情包发送插件",
    "1.0",
)
class MemeSenderPlugin(Star):
    """表情包发送插件"""
    
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        # 加载配置
        if config:
            self.config = config
        else:
            self.config = context.get_config()
        # 每条消息最大表情包数量
        self.max_memes_per_message = self.config.get("max_memes_per_message", 1)
        # 是否清理表情包标签
        self.clean_meme_tags = self.config.get("clean_meme_tags", True)
        # 表情包发送频率（存储为0-100的百分比值）
        self.meme_frequency = self.config.get("meme_frequency", 50)

        # 路径设置
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 初始化组件
        self.config_manager = ConfigManager(self.plugin_dir)
        self.memes_data = {}
        
        # 延迟初始化其他组件，因为需要先加载配置
        self.meme_manager = None

    async def initialize(self):
        """插件初始化方法"""
        try:
            logger.info("开始初始化表情包发送插件...")
            
            # 初始化表情包管理器
            self.meme_manager = MemeManager(self.plugin_dir)
            
            # 加载表情包数据
            await self.load_memes_data()
            
            logger.info(f"表情包发送插件初始化完成，加载了 {len(self.memes_data)} 个表情包分类")
        except Exception as e:
            logger.error(f"表情包发送插件初始化失败: {e}")
            import traceback
            traceback.print_exc()

    async def load_memes_data(self):
        """加载表情包数据"""
        try:
            archive_path = os.path.join(self.plugin_dir, "archive")
            if os.path.exists(archive_path):
                # 遍历archive目录下的所有子目录
                for category in os.listdir(archive_path):
                    category_path = os.path.join(archive_path, category)
                    if os.path.isdir(category_path):
                        # 获取该分类下的所有表情包文件
                        memes = []
                        for file_name in os.listdir(category_path):
                            if file_name.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                                file_path = os.path.join(category_path, file_name)
                                memes.append({
                                    "path": file_path,
                                    "name": file_name
                                })
                        if memes:
                            self.memes_data[category] = memes
                            logger.info(f"加载分类: {category}，包含 {len(memes)} 个表情包")
        except Exception as e:
            logger.error(f"加载表情包数据失败: {e}")

    async def terminate(self):
        """插件销毁方法"""
        logger.info("表情包发送插件正在销毁...")
        # 清理资源
        self.memes_data.clear()

    async def on_config_update(self, config: dict):
        """配置更新回调"""
        try:
            logger.info("收到配置更新，正在同步表情包发送插件配置...")
            
            # 更新配置值
            if "max_memes_per_message" in config:
                self.max_memes_per_message = config["max_memes_per_message"]
                logger.info(f"更新每条消息最大表情包数量: {self.max_memes_per_message}")
            
            if "clean_meme_tags" in config:
                self.clean_meme_tags = config["clean_meme_tags"]
                logger.info(f"更新是否清理表情包标签: {self.clean_meme_tags}")
            
            if "meme_frequency" in config:
                self.meme_frequency = config["meme_frequency"]
                logger.info(f"更新表情包发送频率: {self.meme_frequency}%")
            
            # 这里可以添加其他需要在配置更新时执行的逻辑
            logger.info("表情包发送插件配置同步完成")
        except Exception as e:
            logger.error(f"同步配置时发生错误: {e}")
            import traceback
            traceback.print_exc()

    @filter.on_message()
    async def handle_message(self, event):
        """处理消息事件"""
        try:
            # 获取消息内容
            message_str = event.message_str
            
            # 检查是否包含表情包标签
            if "[meme:" in message_str:
                await self.handle_meme_request(event, message_str)
        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}")

    async def handle_meme_request(self, event, message_str):
        """处理表情包请求"""
        try:
            # 提取表情包标签
            meme_tags = re.findall(r'\[meme:(.*?)\]', message_str)
            
            if not meme_tags:
                return
            
            # 处理每个表情包请求
            for tag in meme_tags:
                # 清理标签
                tag = tag.strip()
                
                # 检查是否有指定分类
                category = None
                meme_name = tag
                if ':' in tag:
                    category, meme_name = tag.split(':', 1)
                    category = category.strip()
                    meme_name = meme_name.strip()
                
                # 发送表情包
                await self.send_meme(event, category, meme_name)
        except Exception as e:
            logger.error(f"处理表情包请求时发生错误: {e}")

    async def send_meme(self, event, category=None, meme_name=None):
        """发送表情包"""
        try:
            # 根据分类和名称选择表情包
            meme_path = await self.select_meme(category, meme_name)
            
            if meme_path:
                # 发送表情包
                await event.result([
                    Image(path=meme_path)
                ])
            else:
                await event.plain_result(f"未找到匹配的表情包: {category}:{meme_name}")
        except Exception as e:
            logger.error(f"发送表情包时发生错误: {e}")

    async def select_meme(self, category=None, meme_name=None):
        """选择表情包"""
        try:
            import random
            
            # 如果指定了分类
            if category and category in self.memes_data:
                category_memes = self.memes_data[category]
                if meme_name:
                    # 尝试根据名称查找
                    for meme in category_memes:
                        if meme_name.lower() in meme["name"].lower():
                            return meme["path"]
                # 随机选择一个
                if category_memes:
                    selected_meme = random.choice(category_memes)
                    return selected_meme["path"]
            elif not category:
                # 随机选择一个分类
                if self.memes_data:
                    random_category = random.choice(list(self.memes_data.keys()))
                    category_memes = self.memes_data[random_category]
                    if category_memes:
                        selected_meme = random.choice(category_memes)
                        return selected_meme["path"]
            
            return None
        except Exception as e:
            logger.error(f"选择表情包时发生错误: {e}")
            return None
