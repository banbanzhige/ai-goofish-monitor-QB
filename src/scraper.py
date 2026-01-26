import asyncio
import json
import os
import random
import hashlib
from datetime import datetime
from urllib.parse import urlencode
from typing import Optional, Dict, Any

from playwright.async_api import (
    Response,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from src.ai_handler import (
    download_all_images,
    get_ai_analysis,
    send_all_notifications,
    cleanup_task_images,
    AICallFailureException,
)
from src.config import (
    AI_DEBUG_MODE,
    API_URL_PATTERN,
    DETAIL_API_URL_PATTERN,
    LOGIN_IS_EDGE,
    RUN_HEADLESS,
    RUNNING_IN_DOCKER,
    SEND_URL_FORMAT_IMAGE,
)
from src.parsers import (
    _parse_search_results_json,
    _parse_user_items_data,
    calculate_reputation_from_ratings,
    parse_ratings_data,
    parse_user_head_data,
)
from src.utils import (
    format_registration_days,
    get_link_unique_key,
    random_sleep,
    safe_get,
    save_to_jsonl,
    log_time,
)

def _default_context_options() -> dict:
    return {
        "user_agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
        "viewport": {"width": 412, "height": 915},
        "device_scale_factor": 2.625,
        "is_mobile": True,
        "has_touch": True,
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "permissions": ["geolocation"],
        "geolocation": {"longitude": 121.4737, "latitude": 31.2304},
        "color_scheme": "light",
    }


def _clean_kwargs(options: dict) -> dict:
    return {k: v for k, v in options.items() if v is not None}


def _looks_like_mobile(ua: str) -> Optional[bool]:
    if not ua:
        return None
    ua_lower = ua.lower()
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        return True
    if "windows" in ua_lower or "macintosh" in ua_lower:
        return False
    return None


def _get_snapshot_user_agent(snapshot: dict) -> Optional[str]:
    if not snapshot:
        return None
    env = snapshot.get("env") or {}
    headers = snapshot.get("headers") or {}
    navigator = env.get("navigator") or {}
    return headers.get("User-Agent") or headers.get("user-agent") or navigator.get("userAgent")


def _should_use_snapshot_env(snapshot: dict) -> bool:
    ua = _get_snapshot_user_agent(snapshot)
    mobile_flag = _looks_like_mobile(ua or "")
    return mobile_flag is not False


def _build_mobile_first_context_overrides(snapshot: dict, allow_device_overrides: bool) -> dict:
    env = snapshot.get("env") or {}
    headers = snapshot.get("headers") or {}
    navigator = env.get("navigator") or {}
    screen = env.get("screen") or {}
    intl = env.get("intl") or {}

    overrides = {}
    ua = _get_snapshot_user_agent(snapshot)
    if allow_device_overrides and ua:
        overrides["user_agent"] = ua

    accept_language = headers.get("Accept-Language") or headers.get("accept-language")
    locale = None
    if accept_language:
        locale = accept_language.split(",")[0].strip()
    elif navigator.get("language"):
        locale = navigator["language"]
    if locale:
        overrides["locale"] = locale

    tz = intl.get("timeZone")
    if tz:
        overrides["timezone_id"] = tz

    if allow_device_overrides:
        width = screen.get("width")
        height = screen.get("height")
        if isinstance(width, (int, float)) and isinstance(height, (int, float)):
            overrides["viewport"] = {"width": int(width), "height": int(height)}

        dpr = screen.get("devicePixelRatio")
        if isinstance(dpr, (int, float)):
            overrides["device_scale_factor"] = float(dpr)

        touch_points = navigator.get("maxTouchPoints")
        if isinstance(touch_points, (int, float)):
            overrides["has_touch"] = touch_points > 0

        mobile_flag = _looks_like_mobile(ua or "")
        if mobile_flag is not None:
            overrides["is_mobile"] = mobile_flag

    return _clean_kwargs(overrides)


def _filter_headers_for_mobile_first(headers: dict, allow_ua_headers: bool) -> dict:
    if allow_ua_headers:
        return headers
    drop_keys = {"user-agent", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform"}
    return {key: value for key, value in headers.items() if key.lower() not in drop_keys}


def _build_mobile_init_script(snapshot: Optional[dict]) -> str:
    snapshot_env = (snapshot or {}).get("env") or {}
    navigator = snapshot_env.get("navigator") or {}
    screen = snapshot_env.get("screen") or {}
    intl = snapshot_env.get("intl") or {}
    use_snapshot_env = _should_use_snapshot_env(snapshot or {})

    payload = {
        "useSnapshot": bool(use_snapshot_env),
        "navigator": {
            "platform": navigator.get("platform"),
            "language": navigator.get("language"),
            "languages": navigator.get("languages"),
            "hardwareConcurrency": navigator.get("hardwareConcurrency"),
            "deviceMemory": navigator.get("deviceMemory"),
            "maxTouchPoints": navigator.get("maxTouchPoints"),
            "doNotTrack": navigator.get("doNotTrack"),
            "userAgentData": navigator.get("userAgentData"),
        },
        "screen": {
            "width": screen.get("width"),
            "height": screen.get("height"),
            "devicePixelRatio": screen.get("devicePixelRatio"),
            "colorDepth": screen.get("colorDepth"),
            "pixelDepth": screen.get("pixelDepth"),
        },
        "intl": {
            "timeZone": intl.get("timeZone"),
            "locale": intl.get("locale"),
        },
    }

    payload_json = json.dumps(payload, ensure_ascii=False)

    return f"""
        // 移除webdriver标识
        Object.defineProperty(navigator, 'webdriver', {{get: () => undefined}});

        // 模拟真实移动设备的navigator属性
        Object.defineProperty(navigator, 'plugins', {{get: () => [1, 2, 3, 4, 5]}});
        Object.defineProperty(navigator, 'languages', {{get: () => ['zh-CN', 'zh', 'en-US', 'en']}});

        // 添加chrome对象
        window.chrome = {{runtime: {{}}, loadTimes: function() {{}}, csi: function() {{}}}};

        // 模拟触摸支持
        Object.defineProperty(navigator, 'maxTouchPoints', {{get: () => 5}});

        // 覆盖permissions查询，避免暴露自动化
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({{state: Notification.permission}}) :
                originalQuery(parameters)
        );

        // 优先模拟移动端，再按快照补充环境细节
        const snapshot = {payload_json};
        if (snapshot && snapshot.useSnapshot) {{
            const nav = snapshot.navigator || {{}};
            if (nav.languages) {{
                Object.defineProperty(navigator, 'languages', {{get: () => nav.languages}});
            }}
            if (nav.language) {{
                Object.defineProperty(navigator, 'language', {{get: () => nav.language}});
            }}
            if (nav.platform) {{
                Object.defineProperty(navigator, 'platform', {{get: () => nav.platform}});
            }}
            if (typeof nav.hardwareConcurrency === 'number') {{
                Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => nav.hardwareConcurrency}});
            }}
            if (typeof nav.deviceMemory === 'number') {{
                Object.defineProperty(navigator, 'deviceMemory', {{get: () => nav.deviceMemory}});
            }}
            if (typeof nav.maxTouchPoints === 'number') {{
                Object.defineProperty(navigator, 'maxTouchPoints', {{get: () => nav.maxTouchPoints}});
            }}
            if (nav.doNotTrack !== undefined && nav.doNotTrack !== null) {{
                Object.defineProperty(navigator, 'doNotTrack', {{get: () => nav.doNotTrack}});
            }}
            if (nav.userAgentData) {{
                Object.defineProperty(navigator, 'userAgentData', {{get: () => nav.userAgentData}});
            }}

            const scr = snapshot.screen || {{}};
            if (typeof scr.width === 'number') {{
                Object.defineProperty(screen, 'width', {{get: () => scr.width}});
            }}
            if (typeof scr.height === 'number') {{
                Object.defineProperty(screen, 'height', {{get: () => scr.height}});
            }}
            if (typeof scr.devicePixelRatio === 'number') {{
                Object.defineProperty(screen, 'devicePixelRatio', {{get: () => scr.devicePixelRatio}});
            }}
            if (typeof scr.colorDepth === 'number') {{
                Object.defineProperty(screen, 'colorDepth', {{get: () => scr.colorDepth}});
            }}
            if (typeof scr.pixelDepth === 'number') {{
                Object.defineProperty(screen, 'pixelDepth', {{get: () => scr.pixelDepth}});
            }}
        }}
    """


def _build_extra_headers(raw_headers: Optional[dict]) -> dict:
    if not raw_headers:
        return {}
    excluded = {"cookie", "content-length"}
    headers = {}
    for key, value in raw_headers.items():
        if not key or key.lower() in excluded or value is None:
            continue
        headers[key] = value
    return headers


COOKIE_ALLOWED_DOMAINS = ("goofish.com",)

def _normalize_same_site_value(raw_value):
    if raw_value is None:
        return "Lax"
    if isinstance(raw_value, str):
        value = raw_value.strip().lower()
        if value in ("none", "lax", "strict"):
            return value.capitalize() if value != "none" else "None"
    return "Lax"

def _is_allowed_cookie_domain(domain: str) -> bool:
    if not domain:
        return False
    domain = domain.lstrip(".").lower()
    for allowed in COOKIE_ALLOWED_DOMAINS:
        allowed_domain = allowed.lstrip(".").lower()
        if domain == allowed_domain or domain.endswith(f".{allowed_domain}"):
            return True
    return False

def _filter_cookies_for_state(raw_cookies):
    """过滤并标准化Cookie，避免混入无关数据。"""
    cleaned_map = {}
    for cookie in raw_cookies or []:
        name = str(cookie.get("name", "")).strip()
        value = cookie.get("value")
        domain = cookie.get("domain", "")
        if not name or value in (None, ""):
            continue
        if not _is_allowed_cookie_domain(domain):
            continue
        expires = cookie.get("expires")
        if not isinstance(expires, (int, float)):
            expires = 0
        clean_cookie = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": cookie.get("path", "/"),
            "expires": expires,
            "httpOnly": bool(cookie.get("httpOnly")),
            "secure": bool(cookie.get("secure")),
            "sameSite": _normalize_same_site_value(cookie.get("sameSite")),
        }
        key = (clean_cookie["name"], clean_cookie["domain"], clean_cookie["path"])
        existing = cleaned_map.get(key)
        if not existing or (existing.get("expires", 0) or 0) < (clean_cookie.get("expires", 0) or 0):
            cleaned_map[key] = clean_cookie
    cleaned_list = list(cleaned_map.values())
    cleaned_list.sort(key=lambda item: (item.get("domain", ""), item.get("name", ""), item.get("path", "")))
    return cleaned_list

def _cookie_fingerprint(cookies) -> str:
    payload = json.dumps(
        [
            {
                "name": cookie.get("name"),
                "value": cookie.get("value"),
                "domain": cookie.get("domain"),
                "path": cookie.get("path"),
                "expires": cookie.get("expires"),
            }
            for cookie in cookies
        ],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _load_account_state(state_file_path: Optional[str]) -> dict:
    if not state_file_path or not os.path.exists(state_file_path):
        return {}
    try:
        with open(state_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"LOG: 读取账号状态文件失败: {e}")
        return {}

def _save_account_state(state_file_path: str, state_data: dict) -> bool:
    try:
        with open(state_file_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"LOG: 写入账号状态文件失败: {e}")
        return False

async def refresh_account_cookies(context, state_file_path: str, last_fingerprint: Optional[str],
                                  account_name: Optional[str], task_name: Optional[str]) -> Optional[str]:
    """每处理一个商品尝试刷新Cookie，仅在发生变化时落盘。"""
    try:
        storage_state = await context.storage_state()
    except Exception as e:
        print(f"LOG: 获取运行中Cookie失败: {e}")
        return last_fingerprint

    filtered_cookies = _filter_cookies_for_state(storage_state.get("cookies", []))
    fingerprint = _cookie_fingerprint(filtered_cookies)
    if last_fingerprint and fingerprint == last_fingerprint:
        return last_fingerprint

    state_data = _load_account_state(state_file_path)
    state_data["cookies"] = filtered_cookies
    state_data["last_cookie_refresh_at"] = datetime.now().isoformat()

    if _save_account_state(state_file_path, state_data):
        if account_name:
            log_time(f"[Cookie刷新] 账号 {account_name} 的Cookie已写回", task_name=task_name)
    return fingerprint


# 统计数据存储目录
STATS_DIR = "task_stats"
os.makedirs(STATS_DIR, exist_ok=True)

def get_task_stats_file(task_name):
    """获取任务统计数据文件名"""
    safe_task_name = "".join(c for c in task_name if c.isalnum() or c in "_-")
    return os.path.join(STATS_DIR, f"{safe_task_name}_stats.json")

def save_task_stats(task_name, processed_count, recommended_count):
    """保存任务统计数据到文件"""
    stats_file = get_task_stats_file(task_name)
    try:
        stats_data = {
            "processed_count": processed_count,
            "recommended_count": recommended_count,
            "timestamp": datetime.now().isoformat()
        }
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存任务统计数据失败: {e}")
        return False

def get_task_stats(task_name):
    """从文件中获取任务统计数据"""
    stats_file = get_task_stats_file(task_name)
    try:
        if os.path.exists(stats_file):
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
            return stats_data["processed_count"], stats_data["recommended_count"]
    except Exception as e:
        print(f"读取任务统计数据失败: {e}")
    return 0, 0

def delete_task_stats_file(task_name):
    """删除任务统计数据文件"""
    stats_file = get_task_stats_file(task_name)
    try:
        if os.path.exists(stats_file):
            os.remove(stats_file)
        return True
    except Exception as e:
        print(f"删除任务统计数据文件失败: {e}")
    return False


def record_risk_control(account_name: Optional[str], reason: str, task_name: Optional[str] = None) -> None:
    if not account_name:
        return
    state_file_path = os.path.join("state", f"{account_name}.json")
    if not os.path.exists(state_file_path):
        return
    try:
        with open(state_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["risk_control_count"] = data.get("risk_control_count", 0) + 1
        history = data.get("risk_control_history", [])
        history.append({
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "task_name": task_name
        })
        data["risk_control_history"] = history[-50:]
        with open(state_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"LOG: 账号 {account_name} 触发风控：{reason}（任务：{task_name or '未知'}）")
    except Exception as e:
        print(f"LOG: 记录风控次数失败: {e}")


async def fetch_user_profile(context, user_id: str) -> dict:
    """
    【新版】访问指定用户的个人主页，按顺序采集其摘要信息、完整的商品列表和完整的评价列表。
    """
    print(f"   -> 开始采集用户ID: {user_id} 的完整信息...")
    profile_data = {}
    page = await context.new_page()

    # 为各项异步任务准备Future和数据容器
    head_api_future = asyncio.get_event_loop().create_future()

    all_items, all_ratings = [], []
    stop_item_scrolling, stop_rating_scrolling = asyncio.Event(), asyncio.Event()

    async def handle_response(response: Response):
        # 捕获头部摘要API
        if "mtop.idle.web.user.page.head" in response.url and not head_api_future.done():
            try:
                head_api_future.set_result(await response.json())
                print(f"      [API捕获] 用户头部信息... 成功")
            except Exception as e:
                if not head_api_future.done(): head_api_future.set_exception(e)

        # 捕获商品列表API
        elif "mtop.idle.web.xyh.item.list" in response.url:
            try:
                data = await response.json()
                all_items.extend(data.get('data', {}).get('cardList', []))
                print(f"      [API捕获] 商品列表... 当前已捕获 {len(all_items)} 件")
                if not data.get('data', {}).get('nextPage', True):
                    stop_item_scrolling.set()
            except Exception as e:
                stop_item_scrolling.set()

        # 捕获评价列表API
        elif "mtop.idle.web.trade.rate.list" in response.url:
            try:
                data = await response.json()
                all_ratings.extend(data.get('data', {}).get('cardList', []))
                print(f"      [API捕获] 评价列表... 当前已捕获 {len(all_ratings)} 条")
                if not data.get('data', {}).get('nextPage', True):
                    stop_rating_scrolling.set()
            except Exception as e:
                stop_rating_scrolling.set()

    page.on("response", handle_response)

    try:
        # --- 任务1: 导航并采集头部信息 ---
        await page.goto(f"https://www.goofish.com/personal?userId={user_id}", wait_until="domcontentloaded", timeout=20000)
        head_data = await asyncio.wait_for(head_api_future, timeout=15)
        profile_data = await parse_user_head_data(head_data)

        # --- 任务2: 滚动加载所有商品 (默认页面) ---
        print("      [采集阶段] 开始采集该用户的商品列表...")
        await random_sleep(2, 4) # 等待第一页商品API完成
        while not stop_item_scrolling.is_set():
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            try:
                await asyncio.wait_for(stop_item_scrolling.wait(), timeout=8)
            except asyncio.TimeoutError:
                print("      [滚动超时] 商品列表可能已加载完毕。")
                break
        profile_data["卖家发布的商品列表"] = await _parse_user_items_data(all_items)

        # --- 任务3: 点击并采集所有评价 ---
        print("      [采集阶段] 开始采集该用户的评价列表...")
        rating_tab_locator = page.locator("//div[text()='信用及评价']/ancestor::li")
        if await rating_tab_locator.count() > 0:
            await rating_tab_locator.click()
            await random_sleep(3, 5) # 等待第一页评价API完成

            while not stop_rating_scrolling.is_set():
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                try:
                    await asyncio.wait_for(stop_rating_scrolling.wait(), timeout=8)
                except asyncio.TimeoutError:
                    print("      [滚动超时] 评价列表可能已加载完毕。")
                    break

            profile_data['卖家收到的评价列表'] = await parse_ratings_data(all_ratings)
            reputation_stats = await calculate_reputation_from_ratings(all_ratings)
            profile_data.update(reputation_stats)
        else:
            print("      [警告] 未找到评价选项卡，跳过评价采集。")

    except Exception as e:
        print(f"   [错误] 采集用户 {user_id} 信息时发生错误: {e}")
    finally:
        page.remove_listener("response", handle_response)
        await page.close()
        print(f"   -> 用户 {user_id} 信息采集完成。")

    return profile_data


async def fetch_xianyu(task_config: dict, debug_limit: int = 0, bound_account: str = None):
    """
    【核心执行器】
    根据单个任务配置，异步浏览闲鱼商品数据，并对每个新发现的商品进行实时的、独立的AI分析和通知。
    
    Args:
        task_config: 任务配置
        debug_limit: 调试模式下的商品处理限制
        bound_account: 绑定的账号名，如果指定则从 state/{bound_account}.json 加载
    """
    keyword = task_config['keyword']
    task_name = task_config.get('task_name', keyword)
    max_pages = task_config.get('max_pages', 1)
    personal_only = task_config.get('personal_only', False)
    min_price = task_config.get('min_price')
    max_price = task_config.get('max_price')
    ai_prompt_text = task_config.get('ai_prompt_text', '')
    free_shipping = bool(task_config.get('free_shipping', False))
    inspection_service = bool(task_config.get('inspection_service', False))
    account_assurance = bool(task_config.get('account_assurance', False))
    super_shop = bool(task_config.get('super_shop', False))
    brand_new = bool(task_config.get('brand_new', False))
    strict_selected = bool(task_config.get('strict_selected', False))
    resale = bool(task_config.get('resale', False))
    raw_new_publish = task_config.get('new_publish_option') or ''
    new_publish_option = raw_new_publish.strip()
    if new_publish_option == '__none__':
        new_publish_option = ''
    region_filter = (task_config.get('region') or '').strip()

    processed_item_count = 0
    recommended_item_count = 0
    stop_scraping = False
    end_reason = "完成了全部设置商品分析"

    processed_links = set()
    output_filename = os.path.join("jsonl", f"{keyword.replace(' ', '_')}_full_data.jsonl")
    if os.path.exists(output_filename):
        print(f"LOG: 发现已存在文件 {output_filename}，正在加载历史记录以去重...")
        try:
            with open(output_filename, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        link = record.get('商品信息', {}).get('商品链接', '')
                        if link:
                            processed_links.add(get_link_unique_key(link))
                    except json.JSONDecodeError:
                        print(f"   [警告] 文件中有一行无法解析为JSON，已跳过。")
            print(f"LOG: 加载完成，已记录 {len(processed_links)} 个已处理过的商品。")
        except IOError as e:
            print(f"   [警告] 读取历史文件时发生错误: {e}")
    else:
        print(f"LOG: 输出文件 {output_filename} 不存在，将创建新文件。")

    async with async_playwright() as p:
        # 访问策略适配启动参数
        launch_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process'
        ]

        if LOGIN_IS_EDGE():
            browser = await p.chromium.launch(headless=RUN_HEADLESS(), channel="msedge", args=launch_args)
        else:
            if RUNNING_IN_DOCKER():
                browser = await p.chromium.launch(headless=RUN_HEADLESS(), args=launch_args)
            else:
                browser = await p.chromium.launch(headless=RUN_HEADLESS(), channel="chrome", args=launch_args)

        # 确定要使用的state文件路径
        # 确定要使用的state文件路径
        current_account_name = None
        if bound_account:
            state_file_path = os.path.join("state", f"{bound_account}.json")
            current_account_name = bound_account
            print(f"LOG: 使用绑定账号 '{bound_account}' 的状态文件: {state_file_path}")
        else:
            # 默认随机选择一个有效账号
            state_dir = "state"
            available_accounts = []
            valid_accounts = []
            current_time = datetime.now().timestamp()
            
            if os.path.exists(state_dir):
                for filename in os.listdir(state_dir):
                    if filename.endswith(".json") and not filename.startswith("_"):
                        account_name = filename[:-5]
                        account_file = os.path.join(state_dir, filename)
                        available_accounts.append(account_name)
                        
                        # 检查账号Cookie是否有效
                        try:
                            with open(account_file, "r", encoding="utf-8") as f:
                                account_data = json.load(f)
                            
                            cookies = account_data.get("cookies", [])
                            is_valid = True
                            
                            # 检查关键Cookie是否过期
                            required_cookies = ["_m_h5_tk", "cookie2", "sgcookie"]
                            for cookie in cookies:
                                if cookie.get("name") in required_cookies:
                                    expires = cookie.get("expires", 0)
                                    if expires > 0 and expires < current_time:
                                        is_valid = False
                                        break
                            
                            if is_valid and cookies:
                                valid_accounts.append(account_name)
                        except Exception as e:
                            print(f"LOG: 检查账号 {account_name} 有效性时出错: {e}")
            
            # 优先选择有效账号
            if valid_accounts:
                selected_account = random.choice(valid_accounts)
                state_file_path = os.path.join("state", f"{selected_account}.json")
                current_account_name = selected_account
                print(f"LOG: 随机选择有效账号 '{selected_account}': {state_file_path}")
                
                # 更新账号最后使用时间
                try:
                    with open(state_file_path, "r", encoding="utf-8") as f:
                        account_data = json.load(f)
                    account_data["last_used_at"] = datetime.now().isoformat()
                    with open(state_file_path, "w", encoding="utf-8") as f:
                        json.dump(account_data, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    print(f"LOG: 更新账号使用时间失败: {e}")
                    
            elif available_accounts:
                # 没有有效账号但有账号存在
                print("\n==================== 无有效Cookie ====================")
                print("所有账号的Cookie均已过期，任务无法执行。")
                print("请在账号管理页面更新Cookie后重试。")
                print("==================================================")
                
                await browser.close()
                return 0, 0, "NO_VALID_COOKIE:所有账号Cookie已过期"
            else:
                # 没有任何账号
                print("\n==================== 无可用账号 ====================")
                print("未找到任何可用账号，任务无法执行。")
                print("请在账号管理页面添加账号后重试。")
                print("==================================================")
                
                await browser.close()
                return 0, 0, "NO_ACCOUNT:无可用账号"

        snapshot_data = None
        cookie_fingerprint = None
        try:
            if os.path.exists(state_file_path):
                with open(state_file_path, "r", encoding="utf-8") as f:
                    snapshot_data = json.load(f)
            else:
                print(f"警告：登录状态文件不存在: {state_file_path}")
        except Exception as e:
            print(f"警告：读取登录状态文件失败，将使用默认配置: {e}")

        context_kwargs = _default_context_options()
        storage_state_arg = state_file_path

        if isinstance(snapshot_data, dict):
            snapshot_cookies = _filter_cookies_for_state(snapshot_data.get("cookies", []))
            cookie_fingerprint = _cookie_fingerprint(snapshot_cookies) if snapshot_cookies else None
            snapshot_data = snapshot_data.copy()
            snapshot_data["cookies"] = snapshot_cookies
            use_snapshot_env = _should_use_snapshot_env(snapshot_data)
            # 新版扩展导出的增强快照，包含环境和Header
            if any(key in snapshot_data for key in ("env", "headers", "page", "storage")):
                print(f"检测到增强浏览器快照，应用环境参数: {state_file_path}")
                storage_state_arg = {"cookies": snapshot_cookies}
                context_kwargs.update(_build_mobile_first_context_overrides(snapshot_data, use_snapshot_env))
                extra_headers = _build_extra_headers(snapshot_data.get("headers"))
                extra_headers = _filter_headers_for_mobile_first(extra_headers, use_snapshot_env)
                if extra_headers:
                    context_kwargs["extra_http_headers"] = extra_headers
            else:
                storage_state_arg = snapshot_data

        context_kwargs = _clean_kwargs(context_kwargs)
        context = await browser.new_context(storage_state=storage_state_arg, **context_kwargs)

        # 增强访问策略适配脚本（移动端优先，按快照补充）
        init_script = _build_mobile_init_script(snapshot_data if isinstance(snapshot_data, dict) else None)
        await context.add_init_script(init_script)
        page = await context.new_page()

        try:
            # 步骤 0 - 模拟真实用户：先访问首页（重要的访问策略适配措施）
            log_time("步骤 0 - 模拟真实用户访问首页...", task_name=task_name)
            await page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
            log_time("[请求间隔优化] 在首页停留，模拟浏览...", task_name=task_name)
            await random_sleep(3, 6)

            # 模拟随机滚动（移动设备的触摸滚动）
            await page.evaluate("window.scrollBy(0, Math.random() * 500 + 200)")
            await random_sleep(1, 2)

            log_time("步骤 1 - 导航到搜索结果页...", task_name=task_name)
            # 使用 'q' 参数构建正确的搜索URL，并进行URL编码
            params = {'q': keyword}
            search_url = f"https://www.goofish.com/search?{urlencode(params)}"
            log_time(f"学习用公开平台URL: {search_url}", task_name=task_name)

            # 使用 expect_response 在导航的同时捕获初始搜索的API数据
            async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=30000) as response_info:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

            initial_response = await response_info.value

            # 等待页面加载出关键筛选元素，以确认已成功进入搜索结果页
            await page.wait_for_selector('text=新发布', timeout=15000)

            # 模拟真实用户行为：页面加载后的初始停留和浏览
            log_time("[请求间隔优化] 模拟用户查看页面...", task_name=task_name)
            await random_sleep(5, 10)

            # --- 新增：检查是否存在验证弹窗 ---
            baxia_dialog = page.locator("div.baxia-dialog-mask")
            middleware_widget = page.locator("div.J_MIDDLEWARE_FRAME_WIDGET")
            try:
                # 等待弹窗在2秒内出现。如果出现，则执行块内代码。
                await baxia_dialog.wait_for(state='visible', timeout=2000)
                print("\n==================== 风控触发 ====================")
                print("检测到页面验证弹窗 (baxia-dialog)，触发风控保护。")
                print(f"任务 '{keyword}' 将在此处中止。")
                print("==================================================")
                end_reason = "RISK_CONTROL:BAXIA_DIALOG"
                record_risk_control(current_account_name, "BAXIA_DIALOG", task_name)
                await browser.close()
                return processed_item_count, recommended_item_count, end_reason
            except PlaywrightTimeoutError:
                # 2秒内弹窗未出现，这是正常情况，继续执行
                pass
            
            # 检查是否有J_MIDDLEWARE_FRAME_WIDGET覆盖层
            try:
                await middleware_widget.wait_for(state='visible', timeout=2000)
                print("\n==================== 风控触发 ====================")
                print("检测到页面验证弹窗 (J_MIDDLEWARE_FRAME_WIDGET)，触发风控保护。")
                print(f"任务 '{keyword}' 将在此处中止。")
                print("==================================================")
                end_reason = "RISK_CONTROL:MIDDLEWARE_WIDGET"
                record_risk_control(current_account_name, "MIDDLEWARE_WIDGET", task_name)
                await browser.close()
                return processed_item_count, recommended_item_count, end_reason
            except PlaywrightTimeoutError:
                # 2秒内弹窗未出现，这是正常情况，继续执行
                pass
            # --- 结束新增 ---

            try:
                await page.click("div[class*='closeIconBg']", timeout=3000)
                print("LOG: 已关闭广告弹窗。")
            except PlaywrightTimeoutError:
                print("LOG: 未检测到广告弹窗。")

            final_response = None
            log_time("步骤 2 - 应用筛选条件...", task_name=task_name)
            if new_publish_option:
                try:
                    await page.click('text=新发布')
                    await random_sleep(1, 2)
                    async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                        await page.click(f"text={new_publish_option}")
                        await random_sleep(2, 4)
                    final_response = await response_info.value
                except PlaywrightTimeoutError:
                    log_time(f"新发布筛选 '{new_publish_option}' 请求超时，继续执行。", task_name=task_name)
                except Exception as e:
                    print(f"LOG: 应用新发布筛选失败: {e}")
            else:
                await page.click('text=新发布')
                await random_sleep(2, 4) # 原来是 (1.5, 2.5)
                async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                    await page.click('text=最新')
                    # --- 修改: 增加排序后的等待时间 ---
                    await random_sleep(4, 7) # 原来是 (3, 5)
                final_response = await response_info.value

            if personal_only:
                async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                    await page.click('text=个人闲置')
                    # --- 修改: 将固定等待改为随机等待，并加长 ---
                    await random_sleep(4, 6) # 原来是 asyncio.sleep(5)
                final_response = await response_info.value

            if free_shipping:
                try:
                    free_shipping_trigger = page.get_by_text("包邮", exact=True)
                    if await free_shipping_trigger.count():
                        async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                            await free_shipping_trigger.first.click()
                            await random_sleep(2, 4)
                        final_response = await response_info.value
                    else:
                        print("LOG: 未找到包邮筛选按钮，跳过。")
                except PlaywrightTimeoutError:
                    log_time("包邮筛选请求超时，继续执行。", task_name=task_name)
                except Exception as e:
                    print(f"LOG: 应用包邮筛选失败: {e}")

            async def apply_extra_filter(label: str, enabled: bool) -> None:
                nonlocal final_response
                if not enabled:
                    return
                try:
                    trigger = page.get_by_text(label, exact=True)
                    if await trigger.count():
                        async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                            await trigger.first.click()
                            await random_sleep(2, 4)
                        final_response = await response_info.value
                    else:
                        print(f"LOG: 未找到{label}筛选按钮，跳过。")
                except PlaywrightTimeoutError:
                    log_time(f"{label}筛选请求超时，继续执行。", task_name=task_name)
                except Exception as e:
                    print(f"LOG: 应用{label}筛选失败: {e}")

            await apply_extra_filter("验货宝", inspection_service)
            await apply_extra_filter("验号担保", account_assurance)
            await apply_extra_filter("超赞鱼小铺", super_shop)
            await apply_extra_filter("全新", brand_new)
            await apply_extra_filter("严选", strict_selected)
            await apply_extra_filter("转卖", resale)

            if region_filter:
                try:
                    area_trigger = page.get_by_text("区域", exact=True)
                    if await area_trigger.count():
                        await area_trigger.first.click()
                        await random_sleep(1.5, 2)
                        popover_candidates = page.locator("div.ant-popover")
                        popover = popover_candidates.filter(has=page.locator(".areaWrap--FaZHsn8E, [class*='areaWrap']")).last
                        if not await popover.count():
                            popover = popover_candidates.filter(has=page.get_by_text("重新定位")).last
                        if not await popover.count():
                            popover = popover_candidates.filter(has=page.get_by_text("查看")).last
                        if not await popover.count():
                            print("LOG: 未找到区域弹窗，跳过区域筛选。")
                            raise PlaywrightTimeoutError("region-popover-not-found")
                        await popover.wait_for(state="visible", timeout=5000)

                        # 列表容器：第一层 children 即省/市/区三列，不再强依赖具体类名，提升鲁棒性
                        area_wrap = popover.locator(".areaWrap--FaZHsn8E, [class*='areaWrap']").first
                        await area_wrap.wait_for(state="visible", timeout=3000)
                        columns = area_wrap.locator(":scope > div")
                        col_prov = columns.nth(0)
                        col_city = columns.nth(1)
                        col_dist = columns.nth(2)

                        region_parts = [p.strip() for p in region_filter.split('/') if p.strip()]
                        city_first_regions = {"北京", "上海", "天津", "重庆"}
                        if region_parts and region_parts[0] in city_first_regions:
                            region_parts = region_parts[:2]

                        async def _click_in_column(column_locator, text_value: str, desc: str) -> None:
                            option = column_locator.locator(".provItem--QAdOx8nD", has_text=text_value).first
                            if await option.count():
                                await option.click()
                                await random_sleep(1.5, 2)
                                try:
                                    await option.wait_for(state="attached", timeout=1500)
                                    await option.wait_for(state="visible", timeout=1500)
                                except PlaywrightTimeoutError:
                                    pass
                            else:
                                print(f"LOG: 未找到{desc} '{text_value}'，跳过。")

                        if len(region_parts) >= 1:
                            await _click_in_column(col_prov, region_parts[0], "省份")
                            await random_sleep(1, 2)
                        if len(region_parts) >= 2:
                            await _click_in_column(col_city, region_parts[1], "城市/区域")
                            await random_sleep(1, 2)
                        if len(region_parts) >= 3:
                            if await col_dist.count():
                                await _click_in_column(col_dist, region_parts[2], "区/县")
                                await random_sleep(1, 2)

                        search_btn = popover.locator("div.searchBtn--Ic6RKcAb").first
                        if await search_btn.count():
                            try:
                                async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                                    await search_btn.click()
                                    await random_sleep(2, 3)
                                final_response = await response_info.value
                            except PlaywrightTimeoutError:
                                log_time("区域筛选提交超时，继续执行。", task_name=task_name)
                        else:
                            print("LOG: 未找到区域弹窗的“查看XX件宝贝”按钮，跳过提交。")
                    else:
                        print("LOG: 未找到区域筛选触发器。")
                except PlaywrightTimeoutError:
                    log_time(f"区域筛选 '{region_filter}' 请求超时，继续执行。", task_name=task_name)
                except Exception as e:
                    print(f"LOG: 应用区域筛选 '{region_filter}' 失败: {e}")

            has_min_price = min_price is not None and str(min_price).strip() != ''
            has_max_price = max_price is not None and str(max_price).strip() != ''
            if has_min_price or has_max_price:
                price_container = page.locator('div[class*="search-price-input-container"]').first
                try:
                    await price_container.wait_for(state="visible", timeout=5000)
                except PlaywrightTimeoutError:
                    print("LOG: 警告 - 价格输入容器不可见，跳过价格筛选。")
                else:
                    try:
                        price_inputs = price_container.get_by_placeholder("￥")
                        if await price_inputs.count() < 2:
                            price_inputs = price_container.get_by_placeholder("¥")
                        if await price_inputs.count() < 2:
                            price_inputs = price_container.locator("input[type='number']")
                        if await price_inputs.count() < 2:
                            print("LOG: 警告 - 未找到价格输入框，跳过价格筛选。")
                        else:
                            if has_min_price:
                                await price_inputs.first.fill(str(min_price), timeout=5000)
                                # --- 修改: 将固定等待改为随机等待 ---
                                await random_sleep(1, 2.5) # 原来是 asyncio.sleep(5)
                            if has_max_price:
                                await price_inputs.nth(1).fill(str(max_price), timeout=5000)
                                # --- 修改: 将固定等待改为随机等待 ---
                                await random_sleep(1, 2.5) # 原来是 asyncio.sleep(5)

                            async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                                await page.keyboard.press('Tab')
                                # --- 修改: 增加确认价格后的等待时间 ---
                                await random_sleep(4, 7) # 原来是 asyncio.sleep(5)
                            final_response = await response_info.value
                    except PlaywrightTimeoutError:
                        print("LOG: 价格筛选输入超时，跳过价格筛选。")

            log_time(
                "Applying filters | "
                f"free_shipping={int(free_shipping)} | "
                f"inspection_service={int(inspection_service)} | "
                f"account_assurance={int(account_assurance)} | "
                f"super_shop={int(super_shop)} | "
                f"brand_new={int(brand_new)} | "
                f"strict_selected={int(strict_selected)} | "
                f"resale={int(resale)} | "
                f"new_publish={new_publish_option or '不限'} | "
                f"region={region_filter or '不限'}",
                task_name=task_name
            )

            log_time("所有筛选已完成，开始处理商品列表...", task_name=task_name)

            current_response = final_response if final_response and final_response.ok else initial_response
            for page_num in range(1, max_pages + 1):
                if stop_scraping: break
                log_time(f"开始处理第 {page_num}/{max_pages} 页 ...", task_name=task_name)

                if page_num > 1:
                    # 查找未被禁用的“下一页”按钮。闲鱼通过添加 'disabled' 类名来禁用按钮，而不是使用 disabled 属性。
                    next_btn = page.locator("[class*='search-pagination-arrow-right']:not([class*='disabled'])")
                    if not await next_btn.count():
                        log_time("已到达最后一页，未找到可用的‘下一页’按钮，停止翻页。", task_name=task_name)
                        break
                    try:
                        async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=20000) as response_info:
                            await next_btn.click()
                            # --- 修改: 增加翻页后的等待时间 ---
                            await random_sleep(5, 8) # 原来是 (1.5, 3.5)
                        current_response = await response_info.value
                    except PlaywrightTimeoutError:
                        log_time(f"翻页到第 {page_num} 页超时，停止翻页。", task_name=task_name)
                        end_reason = "操作终止-结束原因：翻页超时，停止翻页"
                        break

                if not (current_response and current_response.ok):
                    log_time(f"第 {page_num} 页响应无效，跳过。", task_name=task_name)
                    continue

                basic_items = await _parse_search_results_json(await current_response.json(), f"第 {page_num} 页")
                if not basic_items: break

                total_items_on_page = len(basic_items)
                for i, item_data in enumerate(basic_items, 1):
                    if debug_limit > 0 and processed_item_count >= debug_limit:
                        log_time(f"已达到调试上限 ({debug_limit})，停止获取新商品。", task_name=task_name)
                        stop_scraping = True
                        end_reason = f"操作终止-结束原因：已达到调试上限 ({debug_limit})"
                        break

                    unique_key = get_link_unique_key(item_data["商品链接"])
                    if unique_key in processed_links:
                        log_time(f"[页内进度 {i}/{total_items_on_page}] 商品 '{item_data['商品标题'][:20]}...' 已存在，跳过。", task_name=task_name)
                        continue

                    log_time(f"[页内进度 {i}/{total_items_on_page}] 发现新商品，获取详情: {item_data['商品标题'][:30]}...", task_name=task_name)
                    # --- 修改: 访问详情页前的等待时间，模拟用户在列表页上看了一会儿 ---
                    await random_sleep(3, 6) # 原来是 (2, 4)

                    detail_page = await context.new_page()
                    try:
                        async with detail_page.expect_response(lambda r: DETAIL_API_URL_PATTERN in r.url, timeout=25000) as detail_info:
                            await detail_page.goto(item_data["商品链接"], wait_until="domcontentloaded", timeout=25000)

                        detail_response = await detail_info.value
                        if detail_response.ok:
                            detail_json = await detail_response.json()

                            ret_string = str(await safe_get(detail_json, 'ret', default=[]))
                            if "FAIL_SYS_USER_VALIDATE" in ret_string:
                                print("\n==================== 风控触发 ====================")
                                print("检测到系统验证请求 (FAIL_SYS_USER_VALIDATE)")
                                print("触发风控保护机制，任务将立即终止。")
                                print("==================================================")
                                stop_scraping = True
                                end_reason = "RISK_CONTROL:FAIL_SYS_USER_VALIDATE"
                                record_risk_control(current_account_name, "FAIL_SYS_USER_VALIDATE", task_name)
                                await detail_page.close()
                                await browser.close()
                                return processed_item_count, recommended_item_count, end_reason


                            # 解析商品详情数据并更新 item_data
                            item_do = await safe_get(detail_json, 'data', 'itemDO', default={})
                            seller_do = await safe_get(detail_json, 'data', 'sellerDO', default={})

                            reg_days_raw = await safe_get(seller_do, 'userRegDay', default=0)
                            registration_duration_text = format_registration_days(reg_days_raw)

                            # --- START: 新增代码块 ---

                            # 1. 提取卖家的芝麻信用信息
                            zhima_credit_text = await safe_get(seller_do, 'zhimaLevelInfo', 'levelName')

                            # 2. 提取该商品的完整图片列表
                            image_infos = await safe_get(item_do, 'imageInfos', default=[])
                            if image_infos:
                                # 使用列表推导式获取所有有效的图片URL
                                all_image_urls = [img.get('url') for img in image_infos if img.get('url')]
                                if all_image_urls:
                                    # 用新的字段存储图片列表，替换掉旧的单个链接
                                    item_data['商品图片列表'] = all_image_urls
                                    # (可选) 仍然保留主图链接，以防万一
                                    item_data['商品主图链接'] = all_image_urls[0]

                            # --- END: 新增代码块 ---
                            item_data['“想要”人数'] = await safe_get(item_do, 'wantCnt', default=item_data.get('“想要”人数', 'NaN'))
                            item_data['浏览量'] = await safe_get(item_do, 'browseCnt', default='-')
                            # ...[此处可添加更多从详情页解析出的商品信息]...

                            # 调用核心函数采集卖家信息
                            user_profile_data = {}
                            user_id = await safe_get(seller_do, 'sellerId')
                            if user_id:
                                # 新的、高效的调用方式:
                                user_profile_data = await fetch_user_profile(context, str(user_id))
                            else:
                                print("   [警告] 未能从详情API中获取到卖家ID。")
                            user_profile_data['卖家芝麻信用'] = zhima_credit_text
                            user_profile_data['卖家注册时长'] = registration_duration_text

                            # 构建基础记录，包含任务元数据
                            final_record = {
                                "公开信息浏览时间": datetime.now().isoformat(),
                                "搜索关键字": keyword,
                                "任务名称": task_config.get('task_name', 'Untitled Task'),
                                "AI标准": task_config.get('ai_prompt_criteria_file', 'N/A'),
                                "personal_only": personal_only,
                                "free_shipping": free_shipping,
                                "inspection_service": inspection_service,
                                "account_assurance": account_assurance,
                                "super_shop": super_shop,
                                "brand_new": brand_new,
                                "strict_selected": strict_selected,
                                "resale": resale,
                                "new_publish_option": new_publish_option or None,
                                "region": region_filter or None,
                                "商品信息": item_data,
                                "卖家信息": user_profile_data
                            }

                            # --- START: 实时AI分析和通知 ---
                            from src.config import SKIP_AI_ANALYSIS
                            
                            # 检查是否跳过AI分析并直接发送通知
                            if SKIP_AI_ANALYSIS():
                                log_time("环境变量 SKIP_AI_ANALYSIS 已设置，跳过AI分析并直接发送通知...", task_name=task_name)
                                
                                # 当SEND_URL_FORMAT_IMAGE为True时，不需要下载图片
                                downloaded_image_paths = []
                                if not SEND_URL_FORMAT_IMAGE():
                                    # 1. 下载图片
                                    image_urls = item_data.get('商品图片列表', [])
                                    downloaded_image_paths = await download_all_images(item_data['商品ID'], image_urls, task_config.get('task_name', 'default'))
                                    
                                    # 删除下载的图片文件，节省空间
                                    for img_path in downloaded_image_paths:
                                        try:
                                            if os.path.exists(img_path):
                                                os.remove(img_path)
                                                print(f"   [图片] 已删除临时图片文件: {img_path}")
                                        except Exception as e:
                                            print(f"   [图片] 删除图片文件时出错: {e}")
                                
                                # 直接发送通知，将所有商品标记为推荐
                                log_time("商品已跳过AI分析，准备发送通知...", task_name=task_name)
                                await send_all_notifications(item_data, "商品已跳过AI分析，直接通知")
                            else:
                                log_time(f"开始对商品 #{item_data['商品ID']} 进行实时AI分析...", task_name=task_name)
                                
                                # 当SEND_URL_FORMAT_IMAGE为True时，不需要下载图片，直接传递空列表
                                downloaded_image_paths = []
                                if not SEND_URL_FORMAT_IMAGE():
                                    # 1. 下载图片
                                    image_urls = item_data.get('商品图片列表', [])
                                    downloaded_image_paths = await download_all_images(item_data['商品ID'], image_urls, task_config.get('task_name', 'default'))

                                # 2. 获取AI分析
                                ai_analysis_result = None
                                if ai_prompt_text:
                                    try:
                                        # 注意：这里我们将整个记录传给AI，让它拥有最全的上下文
                                        ai_analysis_result = await get_ai_analysis(final_record, downloaded_image_paths, prompt_text=ai_prompt_text)
                                        if ai_analysis_result:
                                            final_record['ai_analysis'] = ai_analysis_result
                                            log_time(f"AI分析完成。推荐状态: {ai_analysis_result.get('is_recommended')}", task_name=task_name)
                                        else:
                                            final_record['ai_analysis'] = {'error': 'AI分析经过多次重试后返回None。'}
                                    except AICallFailureException as e:
                                        print(f"\n==================== AI调用失败 ====================")
                                        print(f"AI调用连续失败，任务 '{task_name}' 将停止。")
                                        print(f"失败原因: {e}")
                                        print("==================================================")
                                        # 删除下载的图片文件
                                        for img_path in downloaded_image_paths:
                                            try:
                                                if os.path.exists(img_path):
                                                    os.remove(img_path)
                                                    print(f"   [图片] 已删除临时图片文件: {img_path}")
                                            except Exception as ex:
                                                print(f"   [图片] 删除图片文件时出错: {ex}")
                                        # 发送任务终止通知
                                        from src.notifier import notifier
                                        await notifier.send_task_completion_notification(task_name, f"AI调用失败-结束原因：{e}", processed_item_count, recommended_item_count)
                                        # 停止任务
                                        stop_scraping = True
                                        end_reason = f"AI_CALL_FAILURE:{e}"
                                        await detail_page.close()
                                        await browser.close()
                                        return processed_item_count, recommended_item_count, end_reason
                                    except Exception as e:
                                        print(f"   -> AI分析过程中发生严重错误: {e}")
                                        final_record['ai_analysis'] = {'error': str(e)}
                                else:
                                    print("   -> 任务未配置AI prompt，跳过分析。")

                                # 删除下载的图片文件，节省空间
                                for img_path in downloaded_image_paths:
                                    try:
                                        if os.path.exists(img_path):
                                            os.remove(img_path)
                                            print(f"   [图片] 已删除临时图片文件: {img_path}")
                                    except Exception as e:
                                        print(f"   [图片] 删除图片文件时出错: {e}")

                                # 3. 如果商品被推荐则发送通知
                                if ai_analysis_result and ai_analysis_result.get('is_recommended'):
                                    log_time("商品被AI推荐，准备发送通知...", task_name=task_name)
                                    # 创建item_data的副本并将ai_analysis添加到其中
                                    item_data_with_analysis = item_data.copy()
                                    item_data_with_analysis['ai_analysis'] = ai_analysis_result
                                    await send_all_notifications(item_data_with_analysis, ai_analysis_result.get("reason", "无"))
                            # --- END: 实时AI分析和通知 ---

                            # 4. 保存包含AI结果的完整记录
                            await save_to_jsonl(final_record, keyword)

                            processed_links.add(unique_key)
                            processed_item_count += 1
                            # 如果商品被推荐，增加推荐计数
                            from src.config import SKIP_AI_ANALYSIS
                            if SKIP_AI_ANALYSIS() or (ai_analysis_result and ai_analysis_result.get('is_recommended')):
                                recommended_item_count += 1
                            log_time(f"商品处理流程完毕。累计处理 {processed_item_count} 个新商品，其中 {recommended_item_count} 个被推荐。", task_name=task_name)
                            
                            # 保存任务统计数据
                            save_task_stats(task_name, processed_item_count, recommended_item_count)

                            # 每处理一个商品尝试刷新Cookie，保持运行期状态最新
                            if current_account_name and state_file_path:
                                cookie_fingerprint = await refresh_account_cookies(
                                    context,
                                    state_file_path,
                                    cookie_fingerprint,
                                    current_account_name,
                                    task_name,
                                )

                            # --- 修改: 增加单个商品处理后的主要延迟 ---
                            log_time("[请求间隔优化] 执行一次主要的随机延迟以模拟用户浏览间隔...", task_name=task_name)
                            await random_sleep(15, 30) # 原来是 (8, 15)，这是最重要的修改之一
                        else:
                            print(f"   错误: 获取商品详情API响应失败，状态码: {detail_response.status}")
                            if AI_DEBUG_MODE:
                                print(f"--- [DETAIL DEBUG] FAILED RESPONSE from {item_data['商品链接']} ---")
                                try:
                                    print(await detail_response.text())
                                except Exception as e:
                                    print(f"无法读取响应内容: {e}")
                                print("----------------------------------------------------")

                    except PlaywrightTimeoutError:
                        print(f"   错误: 访问商品详情页或等待API响应超时。")
                    except Exception as e:
                        print(f"   错误: 处理商品详情时发生未知错误: {e}")
                    finally:
                        await detail_page.close()
                        # --- 修改: 增加关闭页面后的短暂整理时间 ---
                        await random_sleep(2, 4) # 原来是 (1, 2.5)

                # --- 新增: 在处理完一页所有商品后，翻页前，增加一个更长的"休息"时间 ---
                if not stop_scraping and page_num < max_pages:
                    print(f"--- 第 {page_num} 页处理完毕，准备翻页。执行一次页面间的长时休息... ---")
                    await random_sleep(25, 50)

        except PlaywrightTimeoutError as e:
            print(f"\n操作超时错误: 页面元素或网络响应未在规定时间内出现。\n{e}")
            end_reason = f"操作终止-结束原因：操作超时错误: {e}"
        except Exception as e:
            print(f"\n公开信息浏览过程中发生未知错误: {e}")
            end_reason = f"操作终止-结束原因：公开信息浏览过程中发生未知错误: {e}"
        finally:
            log_time("任务执行完毕，浏览器将在5秒后自动关闭...", task_name=task_name)
            await asyncio.sleep(5)
            if debug_limit:
                input("按回车键关闭浏览器...")
            await browser.close()

    # 保存最终的任务统计数据（无论是否处理了商品）
    save_task_stats(task_name, processed_item_count, recommended_item_count)
    
    # 清理任务图片目录
    cleanup_task_images(task_config.get('task_name', 'default'))

    return processed_item_count, recommended_item_count, end_reason
