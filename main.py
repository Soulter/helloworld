from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register

@register("helloworld", "Your Name", "一个简单的 Hello World 插件", "1.0.0", "repo url")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    
    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        '''这是一个 hello world 指令''' # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        yield event.plain_result(f"Hello, {user_name}!") # 发送一条纯文本消息
