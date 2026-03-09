"""
Data Migration Tool - 数据迁移工具

将本地文件数据迁移到 PostgreSQL 数据库。
支持 dry-run 模式和增量迁移。
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage import get_storage, reset_storage
from src.storage.local_adapter import LocalStorageAdapter
from src.storage.postgres_adapter import PostgresAdapter
from src.storage.utils import hash_password, generate_uuid
from src.config import get_env_value, WEB_USERNAME, WEB_PASSWORD

LEGACY_MIGRATION_SCOPE = {
    "will_migrate": [
        {
            "key": "tasks",
            "label": "任务配置",
            "description": "迁移本地任务到 PostgreSQL，归属初始化管理员。",
        },
        {
            "key": "results",
            "label": "监控结果",
            "description": "迁移 jsonl 结果文件到 PostgreSQL，按任务名称匹配。",
        },
        {
            "key": "bayes_profiles",
            "label": "贝叶斯标准",
            "description": "迁移 prompts/bayes 配置到数据库，作为系统级默认标准。",
        },
        {
            "key": "bayes_samples",
            "label": "贝叶斯样本",
            "description": "迁移 prompts/bayes 中样本到数据库，作为系统预置样本。",
        },
        {
            "key": "platform_accounts",
            "label": "平台账号",
            "description": "迁移 state 目录账号到初始化管理员名下。",
        },
    ],
    "will_not_migrate": [
        {
            "key": "user_api_configs",
            "label": "用户私有 API 配置",
            "reason": "本地模式主要使用 .env 全局配置，缺少可可靠分配到用户的来源。",
        },
        {
            "key": "user_notification_configs",
            "label": "用户私有通知渠道",
            "reason": "本地模式主要使用 .env 全局通知配置，缺少可可靠分配到用户的来源。",
        },
        {
            "key": "ai_criteria",
            "label": "AI 标准文本",
            "reason": "当前仍基于 requirement/ 与 criteria/ 文件管理，迁移工具暂未建立文件到用户归属映射。",
        },
        {
            "key": "sessions",
            "label": "登录会话",
            "reason": "会话属于运行态数据，不建议跨存储迁移。",
        },
        {
            "key": "audit_logs",
            "label": "审计日志",
            "reason": "历史日志规模大且结构可能变化，当前迁移流程未纳入。",
        },
    ],
}


MIGRATION_SCOPE = {
    "policy_notice": "本地业务数据默认迁移到 .env 登录账户（WEB_USERNAME）名下；其他账户保持数据隔离。新建用户会自动初始化系统级基础 Prompt/AI 标准、贝叶斯模型和贝叶斯样本。",
    "will_migrate": [
        {
            "key": "tasks",
            "label": "任务配置",
            "description": "迁移本地任务到 PostgreSQL，并归属到 .env 登录账户。",
        },
        {
            "key": "results",
            "label": "监控结果",
            "description": "迁移 jsonl 结果文件到 PostgreSQL，并归属到 .env 登录账户。",
        },
        {
            "key": "prompt_templates",
            "label": "Prompt 模板",
            "description": "迁移 prompts/*.txt 为系统级 Prompt 模板（owner_id=NULL）。",
        },
        {
            "key": "bayes_profiles",
            "label": "贝叶斯模型",
            "description": "迁移 prompts/bayes 模型为系统级基础资源（owner_id=NULL）。",
        },
        {
            "key": "bayes_samples",
            "label": "贝叶斯样本",
            "description": "迁移 prompts/bayes 样本为系统级预置资源（owner_id=NULL）。",
        },
        {
            "key": "platform_accounts",
            "label": "平台账号",
            "description": "迁移 state 目录账号到 .env 登录账户名下。",
        },
        {
            "key": "ai_criteria",
            "label": "AI 标准（Prompt 模板）",
            "description": "迁移 requirement/ 与 criteria/ 文本为系统级 AI 标准（owner_id=NULL）。",
        },
    ],
    "shared_base_assets": [
        {
            "key": "prompt_templates",
            "label": "系统级 Prompt",
            "description": "新用户可直接使用 prompts/ 的基础 Prompt 模板。",
        },
        {
            "key": "ai_criteria",
            "label": "系统级 AI 标准",
            "description": "新用户创建时会自动复制系统级 AI 标准到自己的私有空间。",
        },
        {
            "key": "bayes_profiles",
            "label": "系统级贝叶斯模型",
            "description": "新用户创建时会自动复制系统级贝叶斯模型到自己的私有空间。",
        },
        {
            "key": "bayes_samples",
            "label": "系统级贝叶斯样本",
            "description": "新用户创建时会自动复制系统级贝叶斯样本到自己的私有空间。",
        },
    ],
    "will_not_migrate": [
        {
            "key": "other_users_business_data",
            "label": "其他账户业务数据",
            "reason": "本地历史业务数据不会自动分发到其他账户，以保证数据隔离。",
        },
        {
            "key": "user_api_configs",
            "label": "用户私有 API 配置",
            "reason": "本地模式主要使用 .env 全局配置，缺少可靠用户归属来源。",
        },
        {
            "key": "user_notification_configs",
            "label": "用户私有通知配置",
            "reason": "本地模式主要使用 .env 全局通知配置，缺少可靠用户归属来源。",
        },
        {
            "key": "prompt_files",
            "label": "Prompt 文件的用户级复制",
            "reason": "prompts/ 目录保持系统共享模板，不会按用户复制物理文件。",
        },
        {
            "key": "sessions",
            "label": "登录会话",
            "reason": "会话属于运行态数据，不建议跨存储迁移。",
        },
        {
            "key": "audit_logs",
            "label": "审计日志",
            "reason": "历史日志规模较大且结构可能变化，当前迁移流程未纳入。",
        },
    ],
}


class DataMigrator:
    """数据迁移器"""
    
    def __init__(self, database_url: str, dry_run: bool = False, verbose: bool = False):
        """
        初始化迁移器
        
        Args:
            database_url: PostgreSQL 数据库连接URL
            dry_run: 是否为测试模式（不实际写入数据库）
            verbose: 是否输出详细日志
        """
        self.database_url = database_url
        self.dry_run = dry_run
        self.verbose = verbose
        
        # 初始化存储适配器
        self.local = LocalStorageAdapter()
        self.postgres = PostgresAdapter(database_url)
        
        # 统计
        self.stats = {
            "tasks": {"migrated": 0, "skipped": 0, "errors": 0},
            "results": {"migrated": 0, "skipped": 0, "errors": 0},
            "prompt_templates": {"migrated": 0, "skipped": 0, "errors": 0},
            "bayes_profiles": {"migrated": 0, "skipped": 0, "errors": 0},
            "bayes_samples": {"migrated": 0, "skipped": 0, "errors": 0},
            "ai_criteria": {"migrated": 0, "skipped": 0, "errors": 0},
            "platform_accounts": {"migrated": 0, "skipped": 0, "errors": 0}
        }
    
    def log(self, message: str, level: str = "INFO"):
        """输出日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = "[DRY-RUN] " if self.dry_run else ""
        print(f"[{timestamp}] [{level}] {prefix}{message}")
    
    def log_verbose(self, message: str):
        """输出详细日志"""
        if self.verbose:
            self.log(message, "DEBUG")
    
    def create_tables(self):
        """创建数据库表"""
        self.log("Creating database tables...")
        if not self.dry_run:
            self.postgres.create_tables()
        self.log("Database tables created successfully.")
    
    def create_migration_owner(self, username: str = None, password: str = None) -> Optional[str]:
        """创建迁移归属账户"""
        resolved_username = (username or WEB_USERNAME() or get_env_value("INIT_ADMIN_USERNAME", "admin") or "admin").strip()
        resolved_password = password or WEB_PASSWORD() or get_env_value("INIT_ADMIN_PASSWORD", "admin123") or "admin123"
        email = get_env_value("INIT_ADMIN_EMAIL", "admin@localhost")
        
        self.log(f"Creating migration owner user: {resolved_username}")
        
        if self.dry_run:
            return "dry-run-user-id"
        
        try:
            user = self.postgres.create_user({
                "username": resolved_username,
                "password": resolved_password,
                "email": email,
                "role": "super_admin",
                "is_active": True
            })
            self.log(f"Migration owner user created: {user['id']}")
            return user['id']
        except Exception as e:
            # 用户可能已存在
            self.log(f"Migration owner user may already exist: {e}", "WARNING")
            existing = self.postgres.get_user_by_username(resolved_username)
            if existing:
                return existing['id']
            return None
    
    def migrate_tasks(self, owner_id: Optional[str] = None) -> int:
        """迁移任务配置"""
        self.log("Migrating tasks...")
        
        tasks = self.local.get_tasks()
        self.log(f"Found {len(tasks)} tasks to migrate")
        
        for task in tasks:
            task_name = task.get("task_name", "unknown")
            self.log_verbose(f"Migrating task: {task_name}")
            
            try:
                if not self.dry_run:
                    self.postgres.save_task(task, owner_id)
                self.stats["tasks"]["migrated"] += 1
            except Exception as e:
                self.log(f"Error migrating task {task_name}: {e}", "ERROR")
                self.stats["tasks"]["errors"] += 1
        
        self.log(f"Tasks migrated: {self.stats['tasks']['migrated']}, errors: {self.stats['tasks']['errors']}")
        return self.stats["tasks"]["migrated"]
    
    def migrate_results(self, owner_id: Optional[str] = None) -> int:
        """迁移监控结果"""
        self.log("Migrating monitoring results...")

        tasks = self.local.get_tasks()
        if not tasks:
            self.log("No local tasks found, skip result migration.")
            return 0

        def _normalize_task_name(name: str) -> str:
            """
            标准化任务名用于匹配：
            1. 去掉常见“副本X”后缀
            2. 去掉空白并统一为小写
            """
            raw = str(name or "").strip()
            # 兼容“(副本2)”及其它带数字括号后缀的场景
            normalized = re.sub(r"\s*[\(（][^)\d（(]*\d+[^)]*[\)）]\s*$", "", raw)
            normalized = re.sub(r"\s+", "", normalized)
            return normalized.lower()

        task_name_map = {str(task.get("task_name")): task for task in tasks if task.get("task_name")}
        normalized_task_names: Dict[str, List[str]] = {}
        for task_name in task_name_map.keys():
            key = _normalize_task_name(task_name)
            normalized_task_names.setdefault(key, []).append(task_name)

        result_files = sorted(self.local.jsonl_dir.glob("*_full_data.jsonl"))
        if not result_files:
            self.log("No local jsonl result files found.")
            return 0

        total_results = 0
        for result_file in result_files:
            file_task_name = result_file.stem.replace("_full_data", "")
            target_task_name = file_task_name if file_task_name in task_name_map else None

            # 任务重命名后，尝试使用“去副本后缀”的核心名映射
            if not target_task_name:
                normalized_file_name = _normalize_task_name(file_task_name)
                candidates = normalized_task_names.get(normalized_file_name, [])
                if candidates:
                    target_task_name = candidates[0]
                    self.log(
                        f"  Mapping legacy result file '{result_file.name}' -> task '{target_task_name}'"
                    )

            if not target_task_name:
                self.stats["results"]["skipped"] += 1
                self.log(
                    f"  Skip orphan result file (no matched task): {result_file.name}",
                    "WARNING"
                )
                continue

            file_results = 0
            with open(result_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        result = json.loads(line)
                    except json.JSONDecodeError:
                        self.stats["results"]["errors"] += 1
                        continue

                    try:
                        if not self.dry_run:
                            self.postgres.save_result(target_task_name, result, owner_id)
                        self.stats["results"]["migrated"] += 1
                        total_results += 1
                        file_results += 1
                    except Exception as e:
                        item_id = result.get("商品信息", {}).get("商品ID", "unknown")
                        self.log_verbose(f"Error migrating result {item_id}: {e}")
                        self.stats["results"]["errors"] += 1

            self.log(f"  Migrated {file_results} results from {result_file.name}")

        self.log(
            f"Results migrated: {self.stats['results']['migrated']}, "
            f"skipped_files: {self.stats['results']['skipped']}, "
            f"errors: {self.stats['results']['errors']}"
        )
        return total_results
    
    def migrate_bayes_profiles(self, owner_id: Optional[str] = None) -> int:
        """迁移贝叶斯配置"""
        self.log("Migrating Bayes profiles...")
        
        profiles = self.local.list_bayes_profiles()
        self.log(f"Found {len(profiles)} Bayes profiles to migrate")
        
        for profile_info in profiles:
            version = profile_info.get("version")
            self.log_verbose(f"Migrating Bayes profile: {version}")
            
            try:
                profile = self.local.get_bayes_profile(version)
                if profile and not self.dry_run:
                    # 转换为数据库格式
                    db_profile = {
                        "version": version,
                        "display_name": profile.get("display_name", version),
                        "recommendation_fusion": profile.get("recommendation_fusion"),
                        "bayes_feature_rules": profile.get("bayes_feature_rules"),
                        "is_default": profile.get("is_default", False)
                    }
                    self.postgres.save_bayes_profile(db_profile, owner_id=None)  # 系统配置
                self.stats["bayes_profiles"]["migrated"] += 1
            except Exception as e:
                self.log(f"Error migrating Bayes profile {version}: {e}", "ERROR")
                self.stats["bayes_profiles"]["errors"] += 1
        
        self.log(f"Bayes profiles migrated: {self.stats['bayes_profiles']['migrated']}")
        return self.stats["bayes_profiles"]["migrated"]

    def migrate_prompt_templates(self) -> int:
        """迁移 Prompt 模板（prompts/*.txt）到系统级资源。"""
        self.log("Migrating prompt templates...")
        migrated_total = 0

        try:
            local_templates = self.local.list_prompt_templates(owner_id=None, include_system=True)
        except Exception as exc:
            self.log(f"Load local prompt templates failed: {exc}", "ERROR")
            self.stats["prompt_templates"]["errors"] += 1
            return 0

        self.log(f"Found {len(local_templates)} prompt templates to migrate")
        for template in local_templates:
            template_name = str(template.get("name") or "").strip()
            if not template_name:
                self.stats["prompt_templates"]["skipped"] += 1
                continue

            try:
                existing = None if self.dry_run else self.postgres.get_prompt_template(template_name, owner_id=None)
                if existing:
                    self.stats["prompt_templates"]["skipped"] += 1
                    continue

                local_template = self.local.get_prompt_template(template_name, owner_id=None) or {}
                content = str(local_template.get("content") or "")
                if not content:
                    self.stats["prompt_templates"]["skipped"] += 1
                    continue

                if not self.dry_run:
                    self.postgres.save_prompt_template(
                        {
                            "name": template_name,
                            "content": content,
                            "is_default": bool(local_template.get("is_default", template_name == "base_prompt.txt")),
                        },
                        owner_id=None,
                    )
                self.stats["prompt_templates"]["migrated"] += 1
                migrated_total += 1
            except Exception as exc:
                self.log(f"Error migrating prompt template {template_name}: {exc}", "ERROR")
                self.stats["prompt_templates"]["errors"] += 1

        self.log(
            f"Prompt templates migrated: {self.stats['prompt_templates']['migrated']}, "
            f"skipped: {self.stats['prompt_templates']['skipped']}, "
            f"errors: {self.stats['prompt_templates']['errors']}"
        )
        return migrated_total
    
    def migrate_bayes_samples(self, owner_id: Optional[str] = None) -> int:
        """迁移贝叶斯样本"""
        self.log("Migrating Bayes samples...")
        
        profiles = self.local.list_bayes_profiles()
        total_samples = 0
        
        for profile_info in profiles:
            version = profile_info.get("version")
            
            # 获取样本
            samples = self.local.get_bayes_samples(version)
            self.log(f"  Found {len(samples)} samples for profile {version}")
            
            for sample in samples:
                try:
                    if not self.dry_run:
                        db_sample = {
                            "profile_version": version,
                            "name": sample.get("name", "imported_sample"),
                            "vector": sample.get("vector", []),
                            "label": sample.get("label", 0),
                            "source": sample.get("source", "preset"),
                            "item_id": sample.get("item_id"),
                            "note": sample.get("note")
                        }
                        self.postgres.add_bayes_sample(db_sample, owner_id=None)  # 系统预置
                    self.stats["bayes_samples"]["migrated"] += 1
                    total_samples += 1
                except Exception as e:
                    self.log_verbose(f"Error migrating sample: {e}")
                    self.stats["bayes_samples"]["errors"] += 1
        
        self.log(f"Bayes samples migrated: {self.stats['bayes_samples']['migrated']}")
        return total_samples

    def _load_local_ai_criteria_templates(self) -> List[Dict[str, str]]:
        """读取本地 AI 标准模板（requirement/ + criteria/）。"""
        template_sources = (
            ("requirement", self.local.base_path / "requirement"),
            ("criteria", self.local.base_path / "criteria"),
        )
        templates: List[Dict[str, str]] = []
        for source, directory in template_sources:
            if not directory.exists():
                continue
            for file_path in sorted(directory.glob("*.txt")):
                try:
                    content = file_path.read_text(encoding="utf-8").strip()
                except Exception as exc:
                    self.log_verbose(f"Skip invalid criteria file {file_path}: {exc}")
                    self.stats["ai_criteria"]["errors"] += 1
                    continue
                if not content:
                    self.stats["ai_criteria"]["skipped"] += 1
                    continue
                templates.append(
                    {
                        "source": source,
                        "name": file_path.stem,
                        "content": content,
                    }
                )
        return templates

    def migrate_ai_criteria(self) -> int:
        """迁移 AI 标准文本到系统级资源。"""
        self.log("Migrating AI criteria templates...")
        templates = self._load_local_ai_criteria_templates()
        self.log(f"Found {len(templates)} AI criteria templates to migrate")
        if not templates:
            return 0

        existing_names = set()
        if not self.dry_run:
            try:
                existing_system = self.postgres.list_ai_criteria(owner_id=None, include_system=True)
                existing_names = {item.get("name") for item in existing_system if item.get("name")}
            except Exception as exc:
                self.log(f"Load existing system AI criteria failed: {exc}", "WARNING")

        current_batch_names = set()
        migrated_total = 0
        for template in templates:
            source = str(template.get("source") or "criteria").strip().lower()
            base_name = str(template.get("name") or "").strip()
            if not base_name:
                self.stats["ai_criteria"]["skipped"] += 1
                continue

            if base_name in existing_names:
                self.stats["ai_criteria"]["skipped"] += 1
                continue

            target_name = base_name
            if target_name in current_batch_names:
                target_name = f"{source}_{base_name}"
                suffix = 2
                while target_name in current_batch_names:
                    target_name = f"{source}_{base_name}_{suffix}"
                    suffix += 1

            try:
                if not self.dry_run:
                    self.postgres.save_ai_criteria(
                        {
                            "name": target_name,
                            "content": template.get("content") or "",
                            "is_default": True,
                        },
                        owner_id=None,
                    )
                self.stats["ai_criteria"]["migrated"] += 1
                migrated_total += 1
                current_batch_names.add(target_name)
            except Exception as exc:
                self.log(f"Error migrating AI criteria {target_name}: {exc}", "ERROR")
                self.stats["ai_criteria"]["errors"] += 1

        self.log(
            f"AI criteria migrated: {self.stats['ai_criteria']['migrated']}, "
            f"skipped: {self.stats['ai_criteria']['skipped']}, "
            f"errors: {self.stats['ai_criteria']['errors']}"
        )
        return migrated_total
    
    def migrate_platform_accounts(self, owner_id: str) -> int:
        """迁移平台账号"""
        self.log("Migrating platform accounts...")
        
        accounts = self.local.get_user_platform_accounts("local_admin")
        self.log(f"Found {len(accounts)} platform accounts to migrate")
        
        for account in accounts:
            account_id = account.get("id", "unknown")
            self.log_verbose(f"Migrating account: {account_id}")
            
            try:
                if not self.dry_run:
                    # 转换格式
                    db_account = {
                        "platform": "goofish",
                        "display_name": account.get("display_name", account_id),
                        "cookies": json.dumps(account.get("cookies", {})),
                        "is_active": True
                    }
                    self.postgres.save_user_platform_account(owner_id, db_account)
                self.stats["platform_accounts"]["migrated"] += 1
            except Exception as e:
                self.log(f"Error migrating account {account_id}: {e}", "ERROR")
                self.stats["platform_accounts"]["errors"] += 1
        
        self.log(f"Platform accounts migrated: {self.stats['platform_accounts']['migrated']}")
        return self.stats["platform_accounts"]["migrated"]
    
    def run_full_migration(self, owner_username: str = None, owner_password: str = None):
        """运行完整迁移"""
        self.log("=" * 60)
        self.log("Starting full data migration")
        self.log(f"Dry run: {self.dry_run}")
        self.log("=" * 60)
        
        start_time = datetime.now()
        
        # 1. 创建表
        self.create_tables()
        
        # 2. 创建迁移归属账户
        owner_id = self.create_migration_owner(owner_username, owner_password)
        if not owner_id:
            raise RuntimeError("无法确定迁移归属账户，已终止迁移以避免写入系统共享空间。")
        
        # 3. 迁移任务
        self.migrate_tasks(owner_id)
        
        # 4. 迁移结果
        self.migrate_results(owner_id)
        
        # 5. 迁移 Prompt 模板（系统级）
        self.migrate_prompt_templates()

        # 6. 迁移贝叶斯配置和样本
        self.migrate_bayes_profiles()
        self.migrate_bayes_samples()

        # 7. 迁移 AI 标准（系统级基础资源）
        self.migrate_ai_criteria()

        # 8. 迁移平台账号
        self.migrate_platform_accounts(owner_id)
        
        # 统计
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        self.log("=" * 60)
        self.log("Migration completed!")
        self.log(f"Duration: {duration:.2f} seconds")
        self.log("")
        self.log("Summary:")
        for category, counts in self.stats.items():
            self.log(f"  {category}: migrated={counts['migrated']}, errors={counts['errors']}")
        self.log("=" * 60)
        
        return self.stats

    @staticmethod
    def get_migration_scope() -> Dict[str, Any]:
        """返回数据迁移覆盖范围，供前端展示迁移说明。"""
        return MIGRATION_SCOPE


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Migrate data from local files to PostgreSQL")
    parser.add_argument(
        "--database-url",
        default=get_env_value("DATABASE_URL", ""),
        help="PostgreSQL connection URL (default: from DATABASE_URL env)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual changes)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--owner-username",
        default=WEB_USERNAME() or get_env_value("INIT_ADMIN_USERNAME", "admin"),
        help="Migration owner username (default: WEB_USERNAME)"
    )
    parser.add_argument(
        "--owner-password",
        default=WEB_PASSWORD() or get_env_value("INIT_ADMIN_PASSWORD", ""),
        help="Migration owner password (default: WEB_PASSWORD)"
    )
    parser.add_argument("--admin-username", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--admin-password", default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--create-tables-only",
        action="store_true",
        help="Only create database tables, don't migrate data"
    )
    
    args = parser.parse_args()
    
    if not args.database_url:
        print("Error: DATABASE_URL is required. Set via --database-url or DATABASE_URL env var.")
        sys.exit(1)
    
    # 密码处理
    owner_username = args.owner_username or args.admin_username
    owner_password = args.owner_password or args.admin_password
    if not owner_password and not args.dry_run and not args.create_tables_only:
        import getpass
        owner_password = getpass.getpass("Enter migration owner password: ")
    
    # 运行迁移
    migrator = DataMigrator(
        database_url=args.database_url,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    if args.create_tables_only:
        migrator.create_tables()
        print("Database tables created successfully.")
    else:
        migrator.run_full_migration(owner_username, owner_password)


if __name__ == "__main__":
    main()
