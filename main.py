import re
import uuid
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

GITHUB_URL_PATTERN = r"https://github\.com/[\w\-]+/[\w\-]+(?:/(pull|issues)/\d+)?"
GITHUB_REPO_OPENGRAPH = "https://opengraph.githubassets.com/{hash}/{appendix}"
STAR_HISTORY_URL = "https://api.star-history.com/svg?repos={identifier}&type=Date"


@register("astrbot_plugin_github_sub", "XieMu", "根据群聊中 GitHub 相关链接自动发送 GitHub OpenGraph 图片", "1.0.0", "https://github.com/xiemu-c/astrbot_plugin_github_sub")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)


    @filter.regex(GITHUB_URL_PATTERN)
    async def github_repo(self, event: AstrMessageEvent):
        '''解析 Github 仓库信息'''
        msg = event.message_str
        match = re.search(GITHUB_URL_PATTERN, msg)
        repo_url = match.group(0)
        repo_url = repo_url.replace("https://github.com/", "")
        hash_value = uuid.uuid4().hex
        opengraph_url = GITHUB_REPO_OPENGRAPH.format(hash=hash_value, appendix=repo_url)
        logger.info(f"生成的 OpenGraph URL: {opengraph_url}")

        try:
            yield event.image_result(opengraph_url)
        except Exception as e:
            logger.error(f"下载图片失败: {e}")
            yield event.plain_result("下载 GitHub 图片失败: " + str(e))
            return


@filter.command("ghsub")
async def subscribe_repo(self, event: AstrMessageEvent, repo: str):
    """订阅 GitHub 仓库的 Issue、PR 和评论。例如: /ghsub Soulter/AstrBot"""
    # 验证仓库格式
    if not self._is_valid_repo(repo):
        yield event.plain_result("请提供有效的仓库名，格式为: 用户名/仓库名")
        return

    # 标准化仓库名称（统一大小写）
    normalized_repo = self._normalize_repo_name(repo)

    # 验证仓库是否存在
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                GITHUB_API_URL.format(repo=repo), 
                headers=self._get_github_headers()
            ) as resp:
                if resp.status != 200:
                    yield event.plain_result(f"仓库 {repo} 不存在或无法访问")
                    return
                repo_data = await resp.json()
                display_name = repo_data.get("full_name", repo)
    except Exception as e:
        logger.error(f"验证仓库失败: {e}")
        yield event.plain_result(f"验证仓库时出错: {str(e)}")
        return

    # 获取订阅者唯一标识（如群聊ID或用户ID）
    subscriber_id = event.unified_msg_origin

    # 处理订阅逻辑
    if normalized_repo not in self.subscriptions:
        self.subscriptions[normalized_repo] = []  # 初始化订阅列表

    if subscriber_id not in self.subscriptions[normalized_repo]:
        self.subscriptions[normalized_repo].append(subscriber_id)
        self._save_subscriptions()  # 持久化订阅数据
        
        # 初始化订阅时间戳（用于后续检测新内容）
        self._init_subscription_timestamp(normalized_repo)
        
        yield event.plain_result(f"成功订阅仓库 {display_name} 的更新（Issue/PR/评论）")
    else:
        yield event.plain_result(f"你已订阅仓库 {display_name}")

    # 自动将该仓库设为当前会话的默认仓库
    self.default_repos[subscriber_id] = normalized_repo
    self._save_default_repos()

@filter.command("ghunsub")
async def unsubscribe_repo(self, event: AstrMessageEvent, repo: str = None):
    """取消订阅 GitHub 仓库。例如: /ghunsub Soulter/AstrBot，不提供仓库名则取消所有订阅"""
    subscriber_id = event.unified_msg_origin

    if repo is None:
        # 取消所有订阅
        unsubscribed_repos = []
        # 遍历所有仓库，移除当前订阅者
        for repo_name in list(self.subscriptions.keys()):
            if subscriber_id in self.subscriptions[repo_name]:
                self.subscriptions[repo_name].remove(subscriber_id)
                unsubscribed_repos.append(repo_name)
                # 若仓库无订阅者，删除该仓库记录
                if not self.subscriptions[repo_name]:
                    del self.subscriptions[repo_name]
                    # 清理对应的时间戳
                    self._cleanup_subscription_timestamp(repo_name)
        
        self._save_subscriptions()
        if unsubscribed_repos:
            yield event.plain_result(f"已取消订阅以下仓库: {', '.join(unsubscribed_repos)}")
        else:
            yield event.plain_result("你当前没有订阅任何仓库")
        return

    # 验证仓库格式
    if not self._is_valid_repo(repo):
        yield event.plain_result("请提供有效的仓库名，格式为: 用户名/仓库名")
        return

    # 标准化仓库名称
    normalized_repo = self._normalize_repo_name(repo)
    # 兼容大小写差异（如用户输入大写，实际存储为小写）
    matched_repos = [r for r in self.subscriptions.keys() if r.lower() == normalized_repo.lower()]
    if matched_repos:
        normalized_repo = matched_repos[0]

    # 取消单个仓库订阅
    if normalized_repo in self.subscriptions and subscriber_id in self.subscriptions[normalized_repo]:
        self.subscriptions[normalized_repo].remove(subscriber_id)
        # 若仓库无订阅者，删除记录
        if not self.subscriptions[normalized_repo]:
            del self.subscriptions[normalized_repo]
            self._cleanup_subscription_timestamp(normalized_repo)
        self._save_subscriptions()
        yield event.plain_result(f"已取消订阅仓库 {normalized_repo}")
    else:
        yield event.plain_result(f"你未订阅仓库 {repo}")
