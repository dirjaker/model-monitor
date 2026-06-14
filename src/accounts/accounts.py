"""多账户管理模块"""

import yaml
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from config import load_config, get_api_key
from adapters import get_adapter, BaseModelAdapter, BalanceInfo

logger = logging.getLogger(__name__)


@dataclass
class Account:
    """账户配置"""
    name: str
    provider: str  # deepseek, openrouter, mimo
    api_key: str
    base_url: Optional[str] = None
    is_active: bool = True
    tags: list[str] = field(default_factory=list)


class AccountManager:
    """多账户管理器"""

    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path) if config_path else None
        self.accounts: dict[str, Account] = {}
        self.adapters: dict[str, BaseModelAdapter] = {}
        self._load_accounts()

    def _load_accounts(self):
        """从配置文件加载账户"""
        config = load_config(str(self.config_path) if self.config_path else None)

        # 加载主账户（向后兼容）
        main_config = config.get("deepseek", {})
        api_key = get_api_key(config)
        if api_key:
            self.accounts["default"] = Account(
                name="default",
                provider="deepseek",
                api_key=api_key,
                base_url=main_config.get("base_url"),
                tags=["main"],
            )

        # 加载多账户配置
        accounts_config = config.get("accounts", [])
        for acc_config in accounts_config:
            name = acc_config.get("name")
            if name:
                self.accounts[name] = Account(
                    name=name,
                    provider=acc_config.get("provider", "deepseek"),
                    api_key=acc_config["api_key"],
                    base_url=acc_config.get("base_url"),
                    is_active=acc_config.get("is_active", True),
                    tags=acc_config.get("tags", []),
                )

    def _save_accounts(self):
        """保存账户配置"""
        config = load_config(str(self.config_path) if self.config_path else None)

        # 更新多账户配置
        accounts_list = []
        for name, account in self.accounts.items():
            if name == "default":
                # 更新主账户
                config["deepseek"] = {
                    "api_key": account.api_key,
                    "base_url": account.base_url or "https://api.deepseek.com",
                }
            else:
                accounts_list.append({
                    "name": account.name,
                    "provider": account.provider,
                    "api_key": account.api_key,
                    "base_url": account.base_url,
                    "is_active": account.is_active,
                    "tags": account.tags,
                })

        config["accounts"] = accounts_list

        path = self.config_path or Path(__file__).parent / "config.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        logger.info("账户配置已保存")

    def add_account(
        self,
        name: str,
        provider: str,
        api_key: str,
        base_url: Optional[str] = None,
        tags: list[str] = None,
    ) -> Account:
        """添加账户"""
        if name in self.accounts:
            raise ValueError(f"账户 {name} 已存在")

        account = Account(
            name=name,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            tags=tags or [],
        )
        self.accounts[name] = account
        self._save_accounts()
        logger.info("账户已添加: %s (%s)", name, provider)
        return account

    def remove_account(self, name: str):
        """删除账户"""
        if name == "default":
            raise ValueError("不能删除默认账户")
        if name not in self.accounts:
            raise ValueError(f"账户 {name} 不存在")

        del self.accounts[name]
        if name in self.adapters:
            del self.adapters[name]
        self._save_accounts()
        logger.info("账户已删除: %s", name)

    def update_account(self, name: str, **kwargs):
        """更新账户"""
        if name not in self.accounts:
            raise ValueError(f"账户 {name} 不存在")

        account = self.accounts[name]
        for key, value in kwargs.items():
            if hasattr(account, key):
                setattr(account, key, value)

        # 清除适配器缓存
        if name in self.adapters:
            del self.adapters[name]

        self._save_accounts()

    def get_account(self, name: str) -> Optional[Account]:
        """获取账户"""
        return self.accounts.get(name)

    def list_accounts(self, active_only: bool = True) -> list[Account]:
        """列出账户"""
        accounts = list(self.accounts.values())
        if active_only:
            accounts = [a for a in accounts if a.is_active]
        return accounts

    def get_adapter(self, name: str) -> BaseModelAdapter:
        """获取适配器"""
        if name not in self.adapters:
            account = self.accounts.get(name)
            if not account:
                raise ValueError(f"账户 {name} 不存在")

            self.adapters[name] = get_adapter(
                account.provider,
                api_key=account.api_key,
                base_url=account.base_url,
            )

        return self.adapters[name]

    async def check_all_balances(self) -> dict[str, BalanceInfo]:
        """检查所有账户余额"""
        results = {}
        for name, account in self.accounts.items():
            if not account.is_active:
                continue
            try:
                adapter = self.get_adapter(name)
                results[name] = await adapter.check_balance()
            except Exception as e:
                logger.error("检查账户 %s 余额失败: %s", name, e)
                results[name] = BalanceInfo(total=0, currency="CNY", is_available=False)
        return results

    async def get_total_balance(self) -> dict[str, float]:
        """获取所有账户的总余额（按货币分组）"""
        balances = await self.check_all_balances()
        totals = {}
        for name, balance in balances.items():
            if balance.is_available:
                currency = balance.currency
                totals[currency] = totals.get(currency, 0) + balance.total
        return totals


# 全局账户管理器
_account_manager: Optional[AccountManager] = None


def get_account_manager() -> AccountManager:
    """获取账户管理器单例"""
    global _account_manager
    if _account_manager is None:
        _account_manager = AccountManager()
    return _account_manager
