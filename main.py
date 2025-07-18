import re
import json
import os
import aiohttp
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp

# 订阅数据存储路径
SUBSCRIPTION_FILE = "data/astrbot_plugin_github_sub_subscriptions.json"
# 默认仓库数据存储路径
DEFAULT_REPO_FILE = "data/astrbot_plugin_github_sub_default_repos.json"

GITHUB_URL_PATTERN = r"https://github\.com/[\w\-]+/[\w\-]+(?:/(pull|issues)/\d+)?"
GITHUB_API_URL = "https://api.github.com/repos/{repo}"
GITHUB_ISSUES_API_URL = "https://api.github.com/repos/{repo}/issues"


@register(
    "astrbot_plugin_github_sub",
    "XieMu",
    "GitHub仓库订阅插件",
    "1.0.0", 
    "https://github.com/xiemu-c/astrbot_plugin_github_sub",
)
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        self.subscriptions = self._load_subscriptions()
        self.default_repos = self._load_default_repos()
        self.last_check_time = {}  # 存储每个仓库的最后检查时间
        self.use_lowercase = self.config.get("use_lowercase_repo", True)
        self.github_token = self.config.get("github_token", "")
        self.check_interval = self.config.get("check_interval", 30)

        # 启动后台检查更新任务
        self.task = asyncio.create_task(self._check_updates_periodically())
        logger.info(
            f"GitHub 订阅插件初始化完成，检查间隔: {self.check_interval}分钟"
        )

    def _load_subscriptions(self) -> Dict[str, List[str]]:
        """从JSON文件加载订阅数据"""
        if os.path.exists(SUBSCRIPTION_FILE):
            try:
                with open(SUBSCRIPTION_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载订阅数据失败: {e}")
        return {}

    def _save_subscriptions(self):
        """将订阅数据保存到JSON文件"""
        try:
            os.makedirs(os.path.dirname(SUBSCRIPTION_FILE), exist_ok=True)
            with open(SUBSCRIPTION_FILE, "w", encoding="utf-8") as f:
                json.dump(self.subscriptions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存订阅数据失败: {e}")

    def _load_default_repos(self) -> Dict[str, str]:
        """从JSON文件加载默认仓库设置"""
        if os.path.exists(DEFAULT_REPO_FILE):
            try:
                with open(DEFAULT_REPO_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载默认仓库数据失败: {e}")
        return {}

    def _save_default_repos(self):
        """将默认仓库设置保存到JSON文件"""
        try:
            os.makedirs(os.path.dirname(DEFAULT_REPO_FILE), exist_ok=True)
            with open(DEFAULT_REPO_FILE, "w", encoding="utf-8") as f:
                json.dump(self.default_repos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存默认仓库数据失败: {e}")

    def _normalize_repo_name(self, repo: str) -> str:
        """根据配置标准化仓库名称"""
        return repo.lower() if self.use_lowercase else repo

    def _get_github_headers(self) -> Dict[str, str]:
        """获取带有token（如果有的话）的GitHub API请求头"""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        return headers

    @filter.regex(GITHUB_URL_PATTERN)
    async def github_repo(self, event: AstrMessageEvent):
        """解析 Github 仓库信息"""
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
        """订阅GitHub仓库的Issue和PR。例如: /ghsub Soulter/AstrBot"""
        if not self._is_valid_repo(repo):
            yield event.plain_result("请提供有效的仓库名，格式为: 用户名/仓库名")
            return

        # 标准化仓库名称
        normalized_repo = self._normalize_repo_name(repo)

        # 检查仓库是否存在
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    GITHUB_API_URL.format(repo=repo), headers=self._get_github_headers()
                ) as resp:
                    if resp.status != 200:
                        yield event.plain_result(f"仓库 {repo} 不存在或无法访问")
                        return

                    repo_data = await resp.json()
                    display_name = repo_data.get("full_name", repo)
        except Exception as e:
            logger.error(f"访问GitHub API失败: {e}")
            yield event.plain_result(f"检查仓库时出错: {str(e)}")
            return

        # 获取订阅者唯一标识
        subscriber_id = event.unified_msg_origin

        # 添加或更新订阅
        if normalized_repo not in self.subscriptions:
            self.subscriptions[repo] = []

        if subscriber_id not in self.subscriptions[repo]:
            self.subscriptions[repo].append(subscriber_id)
            self._save_subscriptions()

            # 为新订阅获取初始状态
            await self._fetch_new_items(normalized_repo, None)

            yield event.plain_result(f"成功订阅仓库 {display_name} 的Issue和PR更新")
        else:
            yield event.plain_result(f"你已经订阅了仓库 {display_name}")

        # 设置为当前会话的默认仓库
        self.default_repos[event.unified_msg_origin] = repo
        self._save_default_repos()

    @filter.command("ghunsub")
    async def unsubscribe_repo(self, event: AstrMessageEvent, repo: str = None):
        """取消订阅GitHub仓库。例如: /ghunsub Soulter/AstrBot，不提供仓库名则取消所有订阅"""
        subscriber_id = event.unified_msg_origin

        if repo is None:
            # 取消所有订阅
            unsubscribed = []
            for repo_name, subscribers in list(self.subscriptions.items()):
                if subscriber_id in subscribers:
                    subscribers.remove(subscriber_id)
                    unsubscribed.append(repo_name)
                    if not subscribers:
                        del self.subscriptions[repo_name]

            if unsubscribed:
                self._save_subscriptions()
                yield event.plain_result(
                    f"已取消订阅所有仓库: {', '.join(unsubscribed)}"
                )
            else:
                yield event.plain_result("你没有订阅任何仓库")
            return

        if not self._is_valid_repo(repo):
            yield event.plain_result("请提供有效的仓库名，格式为: 用户名/仓库名")
            return

        # 标准化仓库名称
        normalized_repo = self._normalize_repo_name(repo)

        # 如果使用小写，则不区分大小写查找仓库
        if self.use_lowercase:
            matched_repos = [
                r for r in self.subscriptions.keys() if r.lower() == normalized_repo
            ]
            if matched_repos:
                normalized_repo = matched_repos[0]

        if (
            normalized_repo in self.subscriptions
            and subscriber_id in self.subscriptions[normalized_repo]
        ):
            self.subscriptions[normalized_repo].remove(subscriber_id)
            if not self.subscriptions[normalized_repo]:
                del self.subscriptions[normalized_repo]
            self._save_subscriptions()
            yield event.plain_result(f"已取消订阅仓库 {repo}")
        else:
            yield event.plain_result(f"你没有订阅仓库 {repo}")

    @filter.command("ghlist")
    async def list_subscriptions(self, event: AstrMessageEvent):
        """列出当前订阅的GitHub仓库"""
        subscriber_id = event.unified_msg_origin
        subscribed_repos = []

        for repo, subscribers in self.subscriptions.items():
            if subscriber_id in subscribers:
                subscribed_repos.append(repo)

        if subscribed_repos:
            yield event.plain_result(
                f"你当前订阅的仓库有: {', '.join(subscribed_repos)}"
            )
        else:
            yield event.plain_result("你当前没有订阅任何仓库")

    def _is_valid_repo(self, repo: str) -> bool:
        """检查仓库名称是否有效"""
        return bool(re.match(r"[\w\-]+/[\w\-]+$", repo))

    async def _check_updates_periodically(self):
        """定期检查订阅仓库的更新"""
        try:
            while True:
                try:
                    await self._check_all_repos()
                except Exception as e:
                    logger.error(f"检查仓库更新时出错: {e}")

                # 使用配置的检查间隔
                minutes = max(1, self.check_interval)  # 确保至少1分钟
                logger.debug(f"等待 {minutes} 分钟后再次检查仓库更新")
                await asyncio.sleep(minutes * 60)
        except asyncio.CancelledError:
            logger.info("停止检查仓库更新")

    async def _check_all_repos(self):
        """检查所有订阅仓库的更新"""
        for repo in list(self.subscriptions.keys()):
            logger.info(f"正在检查仓库 {repo} 更新")
            if not self.subscriptions[repo]:  # 如果没有订阅者则跳过
                continue

            try:
                # 获取该仓库的最后检查时间
                last_check = self.last_check_time.get(repo, None)

                # 获取新的issues和PRs
                new_items = await self._fetch_new_items(repo, last_check)

                if new_items:
                    # 更新最后检查时间
                    self.last_check_time[repo] = datetime.now().isoformat()

                    # 通知订阅者有关新内容
                    await self._notify_subscribers(repo, new_items)
            except Exception as e:
                logger.error(f"检查仓库 {repo} 更新时出错: {e}")

    async def _fetch_new_items(self, repo: str, last_check: str):
        """从上次检查以来获取仓库的新issues和PRs"""
        if not last_check:
            # 如果是第一次检查，只记录当前时间并返回空列表
            # 存储为UTC时间戳，不带时区信息以避免比较问题
            self.last_check_time[repo] = (
                datetime.utcnow().replace(microsecond=0).isoformat()
            )
            logger.info(f"初始化仓库 {repo} 的时间戳: {self.last_check_time[repo]}")
            return []

        try:
            # 始终将存储的时间戳视为不带时区信息的UTC时间
            last_check_dt = datetime.fromisoformat(last_check)

            # 确保它被视为简单的datetime
            if hasattr(last_check_dt, "tzinfo") and last_check_dt.tzinfo is not None:
                # 如果它以某种方式具有时区信息，转换为简单的UTC
                last_check_dt = last_check_dt.replace(tzinfo=None)

            logger.info(f"仓库 {repo} 的上次检查时间: {last_check_dt.isoformat()}")
            new_items = []

            # GitHub API在issues端点中同时返回issues和PRs
            async with aiohttp.ClientSession() as session:
                try:
                    params = {
                        "sort": "created",
                        "direction": "desc",
                        "state": "all",
                        "per_page": 10,
                    }
                    async with session.get(
                        GITHUB_ISSUES_API_URL.format(repo=repo),
                        params=params,
                        headers=self._get_github_headers(),
                    ) as resp:
                        if resp.status == 200:
                            items = await resp.json()

                            for item in items:
                                # 将GitHub的时间戳转换为简单的UTC datetime以进行一致的比较
                                github_timestamp = item["created_at"].replace("Z", "")
                                created_at = datetime.fromisoformat(github_timestamp)

                                # 始终移除时区信息以进行比较
                                created_at = created_at.replace(tzinfo=None)

                                logger.info(
                                    f"比较: 仓库 {repo} 的item #{item['number']} 创建于 {created_at.isoformat()}, 上次检查: {last_check_dt.isoformat()}"
                                )

                                if created_at > last_check_dt:
                                    logger.info(
                                        f"发现新的item #{item['number']} in {repo}"
                                    )
                                    new_items.append(item)
                                else:
                                    # 由于项目按创建时间排序，我们可以提前中断
                                    logger.info(f"没有更多新items in {repo}")
                                    break
                        else:
                            logger.error(
                                f"获取仓库 {repo} 的Issue/PR失败: {resp.status}: {await resp.text()}"
                            )
                except Exception as e:
                    logger.error(f"获取仓库 {repo} 的Issue/PR时出错: {e}")

            # 将最后检查时间更新为现在（不带时区信息的UTC）
            if new_items:
                logger.info(f"找到 {len(new_items)} 个新的items在 {repo}")
            else:
                logger.info(f"没有找到新的items在 {repo}")

            # 检查后始终更新时间戳，无论是否找到项目
            self.last_check_time[repo] = (
                datetime.utcnow().replace(microsecond=0).isoformat()
            )
            logger.info(f"更新仓库 {repo} 的时间戳为: {self.last_check_time[repo]}")

            return new_items
        except Exception as e:
            logger.error(f"解析时间时出错: {e}")
            # 如果无法正确解析时间，只需返回空列表
            # 并更新最后检查时间以防止连续错误
            self.last_check_time[repo] = (
                datetime.utcnow().replace(microsecond=0).isoformat()
            )
            logger.info(
                f"出错后更新仓库 {repo} 的时间戳为: {self.last_check_time[repo]}"
            )
            return []

    async def _notify_subscribers(self, repo: str, new_items: List[Dict]):
        """通知订阅者有关新的issues和PRs"""
        if not new_items:
            return

        for subscriber_id in self.subscriptions.get(repo, []):
            try:
                # 创建通知消息
                for item in new_items:
                    item_type = "PR" if "pull_request" in item else "Issue"
                    message = (
                        f"[GitHub更新] 仓库 {repo} 有新的{item_type}:\n"
                        f"#{item['number']} {item['title']}\n"
                        f"作者: {item['user']['login']}\n"
                        f"链接: {item['html_url']}"
                    )

                    # 向订阅者发送消息
                    await self.context.send_message(
                        subscriber_id, Comp.Plain(message)
                    )

                    # 消息之间添加小延迟以避免速率限制
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"向订阅者 {subscriber_id} 发送通知时出错: {e}")

    async def terminate(self):
        """终止前清理并保存数据"""
        self._save_subscriptions()
        self._save_default_repos()
        self.task.cancel()
        logger.info("GitHub 订阅插件 已终止")
