import asyncio
import json
import os
import random
import hashlib
import re
from datetime import datetime
from urllib.parse import urlencode
from typing import Optional, Dict, Any, List, Tuple

from playwright.async_api import (
    Response,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from src.bayes import build_bayes_precalc
from src.ai_handler import (
    get_ai_analysis,
    send_all_notifications,
    cleanup_task_images,
    AICallFailureException,
)
from src.config import (
    AI_DEBUG_MODE,
    API_URL_PATTERN,
    DB_DEDUP_ENABLED,
    DETAIL_API_URL_PATTERN,
    LOGIN_IS_EDGE,
    RUN_HEADLESS,
    RUNNING_IN_DOCKER,
    SKIP_AI_ANALYSIS,
    STORAGE_BACKEND,
)
from src.parsers import (
    _parse_search_results_json,
    _parse_user_items_data,
    calculate_reputation_from_ratings,
    parse_ratings_data,
    parse_user_head_data,
)
from src.utils import (
    build_result_dedup_item_id,
    format_registration_days,
    get_link_unique_key,
    random_sleep,
    safe_get,
    save_to_jsonl,
    log_time,
)

# 新结构下推荐等级的推荐集合（与运行期口径一致）
RECOMMENDED_LEVELS = {"STRONG_BUY", "CAUTIOUS_BUY", "CONDITIONAL_BUY"}


class PriceSortApplyError(Exception):
    """价格排序应用失败（严格失败模式）。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _parse_price_to_number(price_text: Any) -> Optional[float]:
    """将价格文本解析为数值，无法解析或不可比较价格返回 None。"""
    if price_text is None:
        return None

    text = str(price_text).strip()
    if not text:
        return None

    compact = (
        text.replace("当前价", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace("元", "")
        .replace(",", "")
        .replace(" ", "")
        .strip()
    )
    if not compact:
        return None
    if any(token in compact for token in ("面议", "议价", "待议", "咨询")):
        return None

    number_matches = re.findall(r"\d+(?:\.\d+)?", compact)
    if not number_matches:
        return None

    numbers = [float(value) for value in number_matches]
    # 区间价格取均值，避免单边值造成方向误判
    parsed = sum(numbers) / len(numbers)
    if "万" in compact:
        parsed *= 10000

    if parsed <= 0:
        return None
    return parsed


def _normalize_price_bound_value(raw_value: Any) -> Optional[str]:
    """规范化价格筛选值，避免 800.0 在站点输入框中被输入成 8000。"""
    if raw_value is None:
        return None

    text = str(raw_value).strip()
    if not text:
        return None

    int_like_match = re.fullmatch(r"(\d+)\.0+", text)
    if int_like_match:
        return int_like_match.group(1)
    return text


def _extract_price_values_from_search_json(json_data: Any, sample_limit: int = 12) -> List[float]:
    """从搜索响应中抽样提取价格数值序列。"""
    prices: List[float] = []
    if not isinstance(json_data, dict):
        return prices

    result_list = ((json_data.get("data") or {}).get("resultList") or [])
    if not isinstance(result_list, list):
        return prices

    for row in result_list:
        if len(prices) >= sample_limit:
            break
        if not isinstance(row, dict):
            continue
        row_data = row.get("data") or {}
        item_data = row_data.get("item") or {}
        main_data = item_data.get("main") or {}
        ex_content = main_data.get("exContent") or {}

        price_text = ""
        price_parts = ex_content.get("price")
        if isinstance(price_parts, list):
            part_texts = []
            for part in price_parts:
                if isinstance(part, dict):
                    part_text = str(part.get("text") or "").strip()
                    if part_text:
                        part_texts.append(part_text)
            price_text = "".join(part_texts).strip()
        elif isinstance(price_parts, (str, int, float)):
            price_text = str(price_parts).strip()

        parsed_price = _parse_price_to_number(price_text)
        if parsed_price is None:
            continue
        # 忽略异常高价，减少广告位/异常数据对排序方向校验的干扰
        if parsed_price > 5_000_000:
            continue
        prices.append(parsed_price)

    return prices


def _check_price_monotonic(
    prices: List[float],
    order: str,
    tolerance: float = 0.01,
    max_violations: int = 1,
) -> Tuple[bool, int]:
    """校验价格序列是否符合目标单调方向，返回(是否通过, 违例次数)。"""
    if len(prices) < 2:
        return False, 0

    violations = 0
    for prev, curr in zip(prices, prices[1:]):
        if order == "asc":
            if curr + tolerance < prev:
                violations += 1
        else:
            if curr - tolerance > prev:
                violations += 1

    return violations <= max_violations, violations


def _is_ai_recommended(ai_analysis: Optional[Dict[str, Any]]) -> bool:
    """优先基于recommendation_level判断是否推荐，缺失时回退到is_recommended。"""
    if not isinstance(ai_analysis, dict):
        return False
    level = ai_analysis.get("recommendation_level")
    if isinstance(level, str):
        return level in RECOMMENDED_LEVELS
    return ai_analysis.get("is_recommended") is True


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


def _default_desktop_context_options() -> dict:
    """桌面上下文兜底：当移动端命中完整登录页时使用。"""
    return {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "viewport": {"width": 1366, "height": 768},
        "device_scale_factor": 1,
        "is_mobile": False,
        "has_touch": False,
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


def _parse_storage_cookies(raw_cookies: Any) -> list:
    """解析存储层返回的 cookies，兼容 list/JSON字符串/dict 三种结构。"""
    if raw_cookies is None:
        return []
    if isinstance(raw_cookies, list):
        return raw_cookies
    if isinstance(raw_cookies, str):
        try:
            loaded = json.loads(raw_cookies)
            if isinstance(loaded, list):
                return loaded
            if isinstance(loaded, dict):
                value = loaded.get("cookies", [])
                return value if isinstance(value, list) else []
        except Exception:
            return []
    if isinstance(raw_cookies, dict):
        value = raw_cookies.get("cookies", [])
        return value if isinstance(value, list) else []
    return []


def _is_cookie_valid_for_task(cookies: list, current_time: float) -> bool:
    """按采集任务口径判断 Cookie 是否可用。"""
    if not cookies:
        return False
    required_cookies = {"_m_h5_tk", "cookie2", "sgcookie"}
    for cookie in cookies:
        if cookie.get("name") in required_cookies:
            expires = cookie.get("expires", 0)
            if expires and expires > 0 and expires < current_time:
                return False
    return True

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


async def _detect_passport_page_state(page) -> str:
    """识别 passport 页面状态：quick_entry/full_login/none/passport_unknown。"""
    current_url = page.url or ""
    quick_entry_btn = page.locator("text=快速进入").first

    try:
        if await quick_entry_btn.count():
            await quick_entry_btn.wait_for(state="visible", timeout=1200)
            return "quick_entry"
    except PlaywrightTimeoutError:
        pass
    except Exception:
        pass

    if "passport.goofish.com" not in current_url:
        return "none"

    # mini_login 是完整登录页入口；同时兼容页面文案判断。
    if "mini_login" in current_url:
        return "full_login"

    full_login_locators = [
        page.locator("text=请输入手机号").first,
        page.locator("text=获取验证码").first,
        page.locator("text=账号密码登录").first,
        page.locator("input[placeholder*='手机号']").first,
    ]
    for locator in full_login_locators:
        try:
            if await locator.count():
                return "full_login"
        except Exception:
            continue
    return "passport_unknown"


async def _try_passport_quick_entry(page, task_name: str) -> str:
    """仅在“快速进入”确认页执行点击，返回 handled/full_login/none/passport_unknown。"""
    try:
        page_state = await _detect_passport_page_state(page)
        if page_state != "quick_entry":
            return page_state

        log_time("检测到登录确认页，准备点击“快速进入”...", task_name=task_name)
        await random_sleep(1, 3)
        quick_entry_btn = page.locator("text=快速进入").first
        try:
            await quick_entry_btn.click(timeout=5000)
        except PlaywrightTimeoutError:
            # 按钮可能短暂不可点，退化为坐标点击兜底
            box = await quick_entry_btn.bounding_box()
            if box:
                await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await page.wait_for_load_state("domcontentloaded", timeout=20000)
        await random_sleep(1, 2)
        log_time("已尝试通过“快速进入”返回站点，继续原流程...", task_name=task_name)
        return "handled"
    except Exception as e:
        print(f"LOG: 处理登录确认页时出错（忽略继续）：{e}")
        return "passport_unknown"


def _build_cookie_only_storage_state(snapshot_data: Optional[dict], state_file_path: Optional[str]):
    """构造仅含 Cookie 的 storage_state，避免把移动端环境参数带入桌面重试。"""
    if isinstance(snapshot_data, dict):
        snapshot_cookies = _filter_cookies_for_state(snapshot_data.get("cookies", []))
        return {"cookies": snapshot_cookies}
    if state_file_path:
        return state_file_path
    return {"cookies": []}


async def _switch_to_desktop_context_once(
    browser,
    context,
    page,
    snapshot_data: Optional[dict],
    state_file_path: Optional[str],
    task_name: str,
):
    """关闭当前上下文并切到桌面上下文，供登录页兜底重试使用。"""
    log_time("检测到完整登录页，切换桌面上下文重试一次...", task_name=task_name)
    try:
        await page.close()
    except Exception:
        pass
    try:
        await context.close()
    except Exception:
        pass

    desktop_kwargs = _clean_kwargs(_default_desktop_context_options())
    desktop_state = _build_cookie_only_storage_state(snapshot_data, state_file_path)
    new_context = await browser.new_context(storage_state=desktop_state, **desktop_kwargs)
    new_page = await new_context.new_page()
    return new_context, new_page


async def fetch_xianyu(task_config: dict, debug_limit: int = 0, bound_account: str = None):
    """
    【核心执行器】
    根据单个任务配置，异步浏览闲鱼商品数据，并对每个新发现的商品进行实时的、独立的AI分析和通知。
    
    Args:
        task_config: 任务配置
        debug_limit: 调试模式下的商品处理限制
    bound_account: 绑定的账号名，如果指定则从 state/{bound_account}.json 加载
    """
    owner_id = (os.getenv("GOOFISH_OWNER_ID") or "").strip() or None
    keyword = task_config['keyword']
    task_name = task_config.get('task_name', keyword)
    max_pages = task_config.get('max_pages', 1)
    personal_only = task_config.get('personal_only', False)
    min_price = _normalize_price_bound_value(task_config.get('min_price'))
    max_price = _normalize_price_bound_value(task_config.get('max_price'))
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
    raw_price_sort_order = str(task_config.get("price_sort_order") or "").strip().lower()
    price_sort_order = "asc" if raw_price_sort_order == "asc" else "desc"
    region_filter = (task_config.get('region') or '').strip()

    processed_item_count = 0
    recommended_item_count = 0
    stop_scraping = False
    end_reason = "完成了全部设置商品分析"
    db_dedup_enabled = bool(owner_id) and STORAGE_BACKEND() == "postgres" and DB_DEDUP_ENABLED()

    processed_links = set()
    output_filename = os.path.join("jsonl", f"{keyword.replace(' ', '_')}_full_data.jsonl")
    if db_dedup_enabled:
        print("LOG: 已启用数据库去重主路径，启动阶段跳过jsonl历史预加载。")
    elif os.path.exists(output_filename):
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

        # 确定要使用的账号快照（多用户模式优先走存储层，本地模式走 state 文件）
        state_file_path: Optional[str] = None
        snapshot_data = None
        current_account_name = None
        current_time = datetime.now().timestamp()
        owner_storage = None

        if owner_id:
            try:
                from src.storage import get_storage
                owner_storage = get_storage()
            except Exception as e:
                print(f"LOG: 初始化存储层失败，将回退本地 state 文件: {e}")
        use_storage_dedup = bool(db_dedup_enabled and owner_storage is not None)
        if db_dedup_enabled and not use_storage_dedup:
            print("LOG: 数据库去重已开启但存储层不可用，后续将依赖写入阶段处理。")

        if owner_id and owner_storage is not None:
            try:
                storage_accounts = owner_storage.get_user_platform_accounts(owner_id) or []
            except Exception as e:
                print(f"LOG: 读取用户账号失败，将回退本地 state 文件: {e}")
                storage_accounts = []

            if bound_account:
                selected_account_data = next(
                    (acc for acc in storage_accounts if str(acc.get("id")) == str(bound_account)),
                    None
                )
                if selected_account_data is None:
                    print("\n==================== 绑定账号不存在 ====================")
                    print(f"未找到绑定账号 '{bound_account}'，任务无法执行。")
                    print("====================================================")
                    await browser.close()
                    return 0, 0, f"NO_ACCOUNT:绑定账号不存在({bound_account})"

                selected_cookies = _parse_storage_cookies(selected_account_data.get("cookies"))
                if not _is_cookie_valid_for_task(selected_cookies, current_time):
                    print("\n==================== 绑定账号Cookie无效 ====================")
                    print(f"绑定账号 '{bound_account}' 的Cookie已过期或缺失，任务无法执行。")
                    print("请在账号管理页面更新Cookie后重试。")
                    print("========================================================")
                    await browser.close()
                    return 0, 0, f"NO_VALID_COOKIE:绑定账号Cookie无效({bound_account})"

                snapshot_data = {"cookies": _filter_cookies_for_state(selected_cookies)}
                current_account_name = str(
                    selected_account_data.get("display_name")
                    or selected_account_data.get("id")
                    or bound_account
                )
                print(f"LOG: 使用绑定账号 '{current_account_name}' 的数据库快照")

                try:
                    selected_account_data["last_used_at"] = datetime.now().isoformat()
                    owner_storage.save_user_platform_account(owner_id, selected_account_data)
                except Exception as e:
                    print(f"LOG: 更新绑定账号使用时间失败: {e}")
            else:
                available_accounts = []
                valid_accounts = []
                for account_data in storage_accounts:
                    account_id = str(account_data.get("id") or "").strip()
                    if not account_id:
                        continue
                    available_accounts.append(account_data)
                    cookies = _parse_storage_cookies(account_data.get("cookies"))
                    if _is_cookie_valid_for_task(cookies, current_time):
                        valid_accounts.append(account_data)

                if valid_accounts:
                    selected_account_data = random.choice(valid_accounts)
                    selected_cookies = _parse_storage_cookies(selected_account_data.get("cookies"))
                    snapshot_data = {"cookies": _filter_cookies_for_state(selected_cookies)}
                    current_account_name = str(
                        selected_account_data.get("display_name")
                        or selected_account_data.get("id")
                        or "unknown_account"
                    )
                    print(f"LOG: 随机选择有效数据库账号 '{current_account_name}'")
                    try:
                        selected_account_data["last_used_at"] = datetime.now().isoformat()
                        owner_storage.save_user_platform_account(owner_id, selected_account_data)
                    except Exception as e:
                        print(f"LOG: 更新数据库账号使用时间失败: {e}")
                elif available_accounts:
                    print("\n==================== 无有效Cookie ====================")
                    print("所有账号的Cookie均已过期，任务无法执行。")
                    print("请在账号管理页面更新Cookie后重试。")
                    print("==================================================")
                    await browser.close()
                    return 0, 0, "NO_VALID_COOKIE:所有账号Cookie已过期"
                else:
                    print("\n==================== 无可用账号 ====================")
                    print("未找到任何可用账号，任务无法执行。")
                    print("请在账号管理页面添加账号后重试。")
                    print("==================================================")
                    await browser.close()
                    return 0, 0, "NO_ACCOUNT:无可用账号"
        elif bound_account:
            state_file_path = os.path.join("state", f"{bound_account}.json")
            current_account_name = bound_account
            print(f"LOG: 使用绑定账号 '{bound_account}' 的状态文件: {state_file_path}")
        else:
            # 本地模式默认随机选择一个有效账号
            state_dir = "state"
            available_accounts = []
            valid_accounts = []

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
                            if _is_cookie_valid_for_task(cookies, current_time):
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

        cookie_fingerprint = None
        try:
            if snapshot_data is None and state_file_path and os.path.exists(state_file_path):
                with open(state_file_path, "r", encoding="utf-8") as f:
                    snapshot_data = json.load(f)
            elif snapshot_data is None and state_file_path:
                print(f"警告：登录状态文件不存在: {state_file_path}")
        except Exception as e:
            print(f"警告：读取登录状态文件失败，将使用默认配置: {e}")

        context_kwargs = _default_context_options()
        storage_state_arg = state_file_path if state_file_path else {"cookies": []}

        if isinstance(snapshot_data, dict):
            snapshot_cookies = _filter_cookies_for_state(snapshot_data.get("cookies", []))
            cookie_fingerprint = _cookie_fingerprint(snapshot_cookies) if snapshot_cookies else None
            snapshot_data = snapshot_data.copy()
            snapshot_data["cookies"] = snapshot_cookies
            use_snapshot_env = _should_use_snapshot_env(snapshot_data)
            # 新版扩展导出的增强快照，包含环境和Header
            if any(key in snapshot_data for key in ("env", "headers", "page", "storage")):
                snapshot_source = state_file_path if state_file_path else "storage_account"
                print(f"检测到增强浏览器快照，应用环境参数: {snapshot_source}")
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
        desktop_context_retry_used = False

        try:
            # 步骤 0 - 模拟真实用户：先访问首页（重要的访问策略适配措施）
            log_time("步骤 0 - 模拟真实用户访问首页...", task_name=task_name)
            await page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
            # 手动导入Cookie可能进入passport，区分“快速进入确认页”和“完整登录页”
            passport_result = await _try_passport_quick_entry(page, task_name)
            if passport_result == "full_login" and not desktop_context_retry_used:
                context, page = await _switch_to_desktop_context_once(
                    browser,
                    context,
                    page,
                    snapshot_data,
                    state_file_path,
                    task_name,
                )
                desktop_context_retry_used = True
                await page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
                passport_result = await _try_passport_quick_entry(page, task_name)
            if passport_result == "full_login":
                log_time("当前页面为完整登录页，后续将按现有流程继续并等待导航结果。", task_name=task_name)

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
            # 若被引导到登录确认页导致超时，则尝试“快速进入”后重试一次
            initial_response = None
            for attempt in (1, 2):
                try:
                    async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=30000) as response_info:
                        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                    initial_response = await response_info.value
                    break
                except PlaywrightTimeoutError as e:
                    log_time(
                        f"搜索页导航等待响应超时（第{attempt}次），尝试处理登录确认页...",
                        task_name=task_name,
                    )
                    passport_result = await _try_passport_quick_entry(page, task_name)
                    if attempt == 1:
                        if passport_result == "handled":
                            log_time("已处理登录确认页，准备重试搜索页导航...", task_name=task_name)
                            await random_sleep(2, 4)
                            continue
                        if passport_result == "full_login" and not desktop_context_retry_used:
                            context, page = await _switch_to_desktop_context_once(
                                browser,
                                context,
                                page,
                                snapshot_data,
                                state_file_path,
                                task_name,
                            )
                            desktop_context_retry_used = True
                            log_time("已切换桌面上下文，准备重试搜索页导航...", task_name=task_name)
                            await random_sleep(2, 4)
                            continue
                    raise e

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

            price_sort_target_label = "价格从低到高" if price_sort_order == "asc" else "价格从高到低"
            price_sort_retry = 3
            price_sort_applied = False
            price_sort_last_stage = "init"
            price_sort_last_ui_text = ""
            price_sort_last_detail = ""
            price_sort_sample_size = 12
            sort_bar_debug_snapshot: List[Dict[str, Any]] = []
            sort_trigger_debug_snapshot: List[Dict[str, Any]] = []

            def _compact_text(raw_text: str) -> str:
                return (raw_text or "").replace("\n", "").replace("\t", "").replace(" ", "").strip()

            def _state_from_trigger_text(raw_text: str) -> str:
                compact = _compact_text(raw_text)
                has_asc = "价格从低到高" in compact
                has_desc = "价格从高到低" in compact
                # 下拉展开时可能把触发器文本和菜单文本拼在一起，优先按前缀判当前态
                if has_asc and has_desc:
                    if compact.startswith("价格从低到高"):
                        return "asc"
                    if compact.startswith("价格从高到低"):
                        return "desc"
                    if compact.startswith("价格"):
                        return "neutral"
                    asc_idx = compact.find("价格从低到高")
                    desc_idx = compact.find("价格从高到低")
                    return "asc" if asc_idx <= desc_idx else "desc"
                if has_asc:
                    return "asc"
                if has_desc:
                    return "desc"
                if compact.startswith("价格") or compact == "价格":
                    return "neutral"
                return "unknown"

            def _format_simple_debug(items: List[Dict[str, Any]], limit: int = 3) -> str:
                if not items:
                    return "none"
                parts = []
                for index, item in enumerate(items[:limit], start=1):
                    parts.append(
                        f"{index}:{item.get('class', '')}:{item.get('text', '')}@({int(item.get('x', 0))},{int(item.get('y', 0))}) h={int(item.get('h', 0))} score={item.get('score', 0):.2f}"
                    )
                return " | ".join(parts)

            async def _find_sort_bar():
                nonlocal sort_bar_debug_snapshot
                sort_bar_debug_snapshot = []
                bar_candidates = page.locator("div,section,ul,nav")
                count = await bar_candidates.count()
                best_bar = None
                best_score = None
                for index in range(min(count, 160)):
                    bar = bar_candidates.nth(index)
                    try:
                        if not await bar.is_visible():
                            continue
                        text = _compact_text(await bar.inner_text())
                        if "综合" not in text:
                            continue
                        if "新发布" not in text and "新降价" not in text:
                            continue
                        box = await bar.bounding_box()
                        if not box:
                            continue
                        h = float(box.get("height", 0))
                        w = float(box.get("width", 0))
                        if h < 20 or h > 140:
                            continue
                        class_name = str(await bar.get_attribute("class") or "")
                    except Exception:
                        continue

                    score = abs(h - 40) * 1.2 + w * 0.002
                    if "价格" in text:
                        score -= 20
                    if "search-filter-select-container" in class_name:
                        score -= 45
                    if "search-filter-up-container" in class_name:
                        score -= 35
                    if "search-container" in class_name and "search-filter" not in class_name:
                        score += 30

                    candidate_meta = {
                        "class": class_name[:60],
                        "text": text[:30],
                        "x": float(box.get("x", 0)),
                        "y": float(box.get("y", 0)),
                        "h": h,
                        "score": score,
                    }
                    sort_bar_debug_snapshot.append(candidate_meta)

                    if best_bar is None or (best_score is not None and score < best_score):
                        best_bar = bar
                        best_score = score
                sort_bar_debug_snapshot.sort(key=lambda item: item["score"])
                return best_bar

            async def _find_sort_trigger_in_bar(sort_bar):
                nonlocal sort_trigger_debug_snapshot
                sort_trigger_debug_snapshot = []
                if sort_bar is None:
                    return None, ""
                queries = [
                    "[class*='search-select-container'],[class*='search-select-title']",
                    "li,button,div,span,a,p",
                ]
                best_node = None
                best_text = ""
                best_score = None
                seen_keys = set()

                for query in queries:
                    nodes = sort_bar.locator(query)
                    count = await nodes.count()
                    for index in range(min(count, 200)):
                        node = nodes.nth(index)
                        try:
                            if not await node.is_visible():
                                continue
                            text = _compact_text(await node.inner_text())
                            state = _state_from_trigger_text(text)
                            if state == "unknown":
                                continue
                            if "价格" not in text:
                                continue
                            box = await node.bounding_box()
                            if not box:
                                continue
                            class_name = str(await node.get_attribute("class") or "")
                        except Exception:
                            continue

                        key = (int(box.get("x", 0)), int(box.get("y", 0)), text)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)

                        score = min(len(text), 24) * 0.15 + float(box.get("width", 0)) * 0.002
                        if state == "neutral":
                            score -= 6
                        if text == "价格":
                            score -= 8
                        if text.startswith("价格从低到高") or text.startswith("价格从高到低"):
                            score -= 12
                        # 触发器应是短文本，包含两种排序文本的大块节点通常是“触发器+菜单”拼接文本
                        if "价格从低到高" in text and "价格从高到低" in text:
                            score += 80
                        if len(text) > 18:
                            score += 25
                        h = float(box.get("height", 0))
                        if h > 65:
                            score += 40
                        if "search-select-container" in class_name:
                            score -= 20
                        if "search-select-title" in class_name:
                            score -= 10
                        if "search-filter-select-container" in class_name:
                            score += 30

                        sort_trigger_debug_snapshot.append(
                            {
                                "class": class_name[:60],
                                "text": text[:30],
                                "x": float(box.get("x", 0)),
                                "y": float(box.get("y", 0)),
                                "h": float(box.get("height", 0)),
                                "score": score,
                            }
                        )

                        if best_node is None or (best_score is not None and score < best_score):
                            best_node = node
                            best_text = text
                            best_score = score

                sort_trigger_debug_snapshot.sort(key=lambda item: item["score"])
                return best_node, best_text

            async def _get_trigger_state_and_text():
                sort_bar = await _find_sort_bar()
                trigger, trigger_text = await _find_sort_trigger_in_bar(sort_bar)
                return _state_from_trigger_text(trigger_text), trigger_text, trigger, sort_bar

            async def _release_focus_after_new_publish():
                try:
                    await page.evaluate(
                        "() => { const el = document.activeElement; if (el && typeof el.blur === 'function') el.blur(); }"
                    )
                except Exception:
                    pass
                try:
                    await page.mouse.click(8, 8)
                except Exception:
                    pass
                await random_sleep(0.2, 0.4)

            async def _find_sort_menu(trigger_node):
                menu_candidates = page.locator(
                    "xpath=//*[self::div or self::ul or self::section][contains(normalize-space(.), '价格从低到高') and contains(normalize-space(.), '价格从高到低')]"
                )
                count = await menu_candidates.count()
                trigger_box = None
                if trigger_node is not None:
                    try:
                        trigger_box = await trigger_node.bounding_box()
                    except Exception:
                        trigger_box = None

                best_menu = None
                best_score = None
                for index in range(min(count, 24)):
                    menu = menu_candidates.nth(index)
                    try:
                        if not await menu.is_visible():
                            continue
                        text = _compact_text(await menu.inner_text())
                        if "价格从低到高" not in text or "价格从高到低" not in text:
                            continue
                        box = await menu.bounding_box()
                        if not box:
                            continue
                    except Exception:
                        continue

                    score = float(box.get("width", 0)) * float(box.get("height", 0)) * 0.001
                    if trigger_box:
                        trigger_x = float(trigger_box.get("x", 0)) + float(trigger_box.get("width", 0)) / 2
                        trigger_y = float(trigger_box.get("y", 0)) + float(trigger_box.get("height", 0))
                        center_x = float(box.get("x", 0)) + float(box.get("width", 0)) / 2
                        center_y = float(box.get("y", 0))
                        if center_y + 3 < trigger_y:
                            continue
                        score += abs(center_x - trigger_x) * 0.03 + abs(center_y - trigger_y) * 0.1
                    if best_menu is None or (best_score is not None and score < best_score):
                        best_menu = menu
                        best_score = score
                return best_menu

            async def _wait_sort_menu(trigger_node, timeout_ms: int = 2500):
                deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
                while asyncio.get_event_loop().time() < deadline:
                    menu = await _find_sort_menu(trigger_node)
                    if menu is not None:
                        return menu
                    await asyncio.sleep(0.12)
                return None

            async def _collect_option_candidates(menu, option_label: str, source: str = "menu", limit: int = 3):
                nodes = menu.locator("li,button,a,span,div,p")
                count = await nodes.count()
                candidates = []
                for strict_mode in (True, False):
                    candidates = []
                    for index in range(min(count, 120)):
                        node = nodes.nth(index)
                        try:
                            if not await node.is_visible():
                                continue
                            text = _compact_text(await node.inner_text())
                            if option_label not in text:
                                continue
                            if strict_mode and len(text) > len(option_label) + 6:
                                continue
                            box = await node.bounding_box()
                            if not box:
                                continue
                        except Exception:
                            continue
                        score = 0.0
                        if text != option_label:
                            score += 6
                        score += min(len(text), 24) * 0.1
                        score += float(box.get("width", 0)) * 0.002
                        candidates.append(
                            {
                                "node": node,
                                "text": text,
                                "x": float(box.get("x", 0)),
                                "y": float(box.get("y", 0)),
                                "score": score,
                                "source": source,
                            }
                        )
                    if candidates:
                        break
                candidates.sort(key=lambda item: item["score"])
                return candidates[:limit]

            def _format_candidate_debug(candidates):
                if not candidates:
                    return "none"
                parts = []
                for index, item in enumerate(candidates, start=1):
                    parts.append(
                        f"{index}:{item['source']}:{item['text']}@({int(item['x'])},{int(item['y'])}) score={item['score']:.2f}"
                    )
                return " | ".join(parts)

            async def _open_price_sort_panel(trigger_node):
                menu = await _find_sort_menu(trigger_node)
                if menu is not None:
                    return menu
                if trigger_node is None:
                    return None
                await trigger_node.click(timeout=3000)
                await random_sleep(0.25, 0.45)
                menu = await _wait_sort_menu(trigger_node, timeout_ms=2500)
                if menu is not None:
                    return menu
                try:
                    await trigger_node.click(timeout=3000, force=True)
                except Exception:
                    pass
                await random_sleep(0.25, 0.45)
                return await _wait_sort_menu(trigger_node, timeout_ms=1800)

            async def _click_sort_option_in_menu(menu, option_label: str, attempt: int, timeout_ms: int = 12000):
                top_candidates = await _collect_option_candidates(menu, option_label, source="menu", limit=3)
                if not top_candidates:
                    preview_nodes = await _collect_option_candidates(menu, "价格从", source="menu_preview", limit=3)
                    raise RuntimeError(
                        f"option_not_found:target_not_found candidates={_format_candidate_debug(preview_nodes)}"
                    )

                chosen = top_candidates[0]
                log_time(
                    f"价格排序第{attempt}/{price_sort_retry}次 stage=click_sent target={option_label} candidate={chosen['text']}",
                    task_name=task_name,
                )
                async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=timeout_ms) as response_info:
                    await chosen["node"].click(timeout=3000)
                    await random_sleep(0.8, 1.2)
                return await response_info.value, top_candidates

            await _release_focus_after_new_publish()

            for attempt in range(1, price_sort_retry + 1):
                try:
                    current_state, trigger_text, trigger_node, sort_bar = await _get_trigger_state_and_text()
                    price_sort_last_ui_text = trigger_text
                    log_time(
                        f"价格排序第{attempt}/{price_sort_retry}次 stage=state_detected state={current_state} trigger={trigger_text or 'n/a'}",
                        task_name=task_name,
                    )
                    if current_state == price_sort_order:
                        price_sort_applied = True
                        log_time(
                            f"价格排序已是目标状态，跳过点击：target={price_sort_target_label} state={current_state}",
                            task_name=task_name,
                        )
                        break

                    if sort_bar is None or trigger_node is None:
                        price_sort_last_stage = "open_panel"
                        price_sort_last_detail = (
                            "未定位到排序条或价格触发器 "
                            f"bar_candidates={_format_simple_debug(sort_bar_debug_snapshot)} "
                            f"trigger_candidates={_format_simple_debug(sort_trigger_debug_snapshot)}"
                        )
                        log_time(
                            f"价格排序第{attempt}/{price_sort_retry}次 stage=open_panel failed detail={price_sort_last_detail}",
                            task_name=task_name,
                        )
                        await random_sleep(1, 2)
                        continue

                    sort_menu = await _open_price_sort_panel(trigger_node)
                    if sort_menu is None:
                        price_sort_last_stage = "open_panel"
                        price_sort_last_detail = "价格排序下拉未展开"
                        log_time(
                            f"价格排序第{attempt}/{price_sort_retry}次 stage=open_panel failed detail={price_sort_last_detail} trigger={trigger_text or 'n/a'}",
                            task_name=task_name,
                        )
                        await random_sleep(1, 2)
                        continue
                    log_time(
                        f"价格排序第{attempt}/{price_sort_retry}次 stage=open_panel success trigger={trigger_text or 'n/a'}",
                        task_name=task_name,
                    )

                    try:
                        sort_response, top_candidates = await _click_sort_option_in_menu(
                            sort_menu,
                            price_sort_target_label,
                            attempt=attempt,
                            timeout_ms=12000,
                        )
                    except RuntimeError as scoped_error:
                        if str(scoped_error).startswith("option_not_found"):
                            price_sort_last_stage = "option_not_found"
                            price_sort_last_detail = str(scoped_error)
                            log_time(
                                f"价格排序第{attempt}/{price_sort_retry}次 stage=option_not_found detail={price_sort_last_detail}",
                                task_name=task_name,
                            )
                            await random_sleep(1, 2)
                            continue
                        raise

                    if not sort_response or not sort_response.ok:
                        price_sort_last_stage = "response_miss"
                        status_code = getattr(sort_response, "status", "unknown")
                        price_sort_last_detail = (
                            f"响应状态异常 status={status_code} candidates={_format_candidate_debug(top_candidates)}"
                        )
                        log_time(
                            f"价格排序第{attempt}/{price_sort_retry}次 stage=response_miss detail={price_sort_last_detail}",
                            task_name=task_name,
                        )
                        await random_sleep(1, 2)
                        continue

                    final_response = sort_response
                    # 关闭下拉焦点后再判状态，避免读取到“触发器+菜单”拼接文本
                    await _release_focus_after_new_publish()
                    current_state, trigger_text, _, _ = await _get_trigger_state_and_text()
                    price_sort_last_ui_text = trigger_text
                    if current_state != price_sort_order:
                        price_sort_last_stage = "ui_not_changed"
                        price_sort_last_detail = f"UI状态未切换到目标值 current_state={current_state}"
                        log_time(
                            f"价格排序第{attempt}/{price_sort_retry}次 stage=ui_not_changed detail={price_sort_last_detail} trigger={trigger_text or 'n/a'}",
                            task_name=task_name,
                        )
                        await random_sleep(1, 2)
                        continue

                    sample_prices: List[float] = []
                    try:
                        response_json = await sort_response.json()
                        sample_prices = _extract_price_values_from_search_json(
                            response_json,
                            sample_limit=price_sort_sample_size,
                        )
                    except Exception as e:
                        price_sort_last_stage = "monotonic_check_failed"
                        price_sort_last_detail = f"读取排序响应JSON失败: {e}"
                        log_time(
                            f"价格排序第{attempt}/{price_sort_retry}次 stage=monotonic_check_failed detail={price_sort_last_detail}",
                            task_name=task_name,
                        )
                        await random_sleep(1, 2)
                        continue

                    monotonic_ok, violations = _check_price_monotonic(sample_prices, price_sort_order)
                    if not monotonic_ok:
                        price_sort_last_stage = "monotonic_check_failed"
                        if len(sample_prices) < 2:
                            price_sort_last_detail = f"可用抽样价格不足 sample_count={len(sample_prices)}"
                        else:
                            price_sort_last_detail = (
                                f"单调性校验失败 sample_count={len(sample_prices)} violations={violations}"
                            )
                        log_time(
                            f"价格排序第{attempt}/{price_sort_retry}次 stage=monotonic_check_failed detail={price_sort_last_detail}",
                            task_name=task_name,
                        )
                        await random_sleep(1, 2)
                        continue

                    price_sort_applied = True
                    first_price = sample_prices[0] if sample_prices else "n/a"
                    last_price = sample_prices[-1] if sample_prices else "n/a"
                    log_time(
                        f"价格排序成功：target={price_sort_order} final_state={current_state} sample_count={len(sample_prices)} first_price={first_price} last_price={last_price}",
                        task_name=task_name,
                    )
                    break
                except PlaywrightTimeoutError as e:
                    price_sort_last_stage = "response_miss"
                    price_sort_last_detail = f"等待搜索响应超时: {e}"
                    log_time(
                        f"价格排序第{attempt}/{price_sort_retry}次 stage=response_miss detail={price_sort_last_detail}",
                        task_name=task_name,
                    )
                except Exception as e:
                    price_sort_last_stage = "exception"
                    price_sort_last_detail = str(e)
                    log_time(
                        f"价格排序第{attempt}/{price_sort_retry}次 stage=exception detail={price_sort_last_detail}",
                        task_name=task_name,
                    )

            if not price_sort_applied:
                reason_message = (
                    f"target={price_sort_order} stage={price_sort_last_stage} retries={price_sort_retry} "
                    f"last_ui={price_sort_last_ui_text or 'n/a'} detail={price_sort_last_detail or 'n/a'}"
                )
                log_time(
                    f"价格排序失败并中断任务 code=PRICE_SORT_NOT_APPLIED {reason_message}",
                    task_name=task_name,
                )
                raise PriceSortApplyError("PRICE_SORT_NOT_APPLIED", reason_message)

            has_min_price = min_price is not None and str(min_price).strip() != ''
            has_max_price = max_price is not None and str(max_price).strip() != ''
            if has_min_price or has_max_price:
                price_container = page.locator('div[class*="search-price-input-container"]').first
                max_price_retry = 3
                price_filter_applied = False

                async def _open_price_filter_panel() -> bool:
                    if await price_container.is_visible():
                        return True

                    # 先尝试点“价格”标签展开输入面板，降低定位到隐藏输入框的概率
                    trigger_candidates = [
                        page.get_by_text("价格", exact=True).first,
                        page.locator("div[class*='sort']", has_text="价格").first,
                        page.locator("span", has_text="价格").first,
                    ]
                    for trigger in trigger_candidates:
                        try:
                            if await trigger.count() < 1 or not await trigger.is_visible():
                                continue
                            await trigger.click(timeout=3000)
                            await random_sleep(0.8, 1.5)
                            if await price_container.is_visible():
                                return True
                        except Exception:
                            continue

                    try:
                        await price_container.wait_for(state="visible", timeout=3000)
                        return True
                    except PlaywrightTimeoutError:
                        return False

                async def _resolve_price_inputs():
                    # 优先使用语义化占位符，其次回退到可见可编辑输入框
                    min_input = price_container.get_by_placeholder("最低价").first
                    max_input = price_container.get_by_placeholder("最高价").first
                    try:
                        if (
                            await min_input.count() > 0
                            and await max_input.count() > 0
                            and await min_input.is_visible()
                            and await max_input.is_visible()
                            and await min_input.is_editable()
                            and await max_input.is_editable()
                        ):
                            return min_input, max_input
                    except Exception:
                        pass

                    visible_editable_inputs = []
                    input_candidates = price_container.locator("input")
                    candidate_count = await input_candidates.count()
                    for idx in range(min(candidate_count, 8)):
                        candidate = input_candidates.nth(idx)
                        try:
                            if await candidate.is_visible() and await candidate.is_editable():
                                visible_editable_inputs.append(candidate)
                        except Exception:
                            continue
                    if len(visible_editable_inputs) >= 2:
                        return visible_editable_inputs[0], visible_editable_inputs[1]
                    return None, None

                def _normalize_price_input_text(text: str) -> str:
                    return re.sub(r"[^\d.]", "", str(text or "").strip())

                async def _fill_price_input(input_node, expected_value, label: str) -> str:
                    expected_text = _normalize_price_bound_value(expected_value) or ""
                    await input_node.click(timeout=3000)
                    # 先清空再填充，避免和历史值拼接
                    await input_node.fill("", timeout=3000)
                    await random_sleep(0.15, 0.35)
                    await input_node.fill(expected_text, timeout=5000)
                    await random_sleep(0.15, 0.35)

                    actual_text = ""
                    try:
                        actual_text = str(await input_node.input_value()).strip()
                    except Exception:
                        actual_text = ""

                    # 回读不一致时，回退到“全选+输入”再尝试一次
                    if _normalize_price_input_text(actual_text) != _normalize_price_input_text(expected_text):
                        try:
                            await input_node.click(timeout=3000)
                            await input_node.press("Control+A", timeout=3000)
                            await input_node.type(expected_text, delay=25, timeout=5000)
                            await random_sleep(0.15, 0.35)
                            actual_text = str(await input_node.input_value()).strip()
                        except Exception:
                            pass

                    log_time(
                        f"价格筛选输入回读 {label}: expected={expected_text} actual={actual_text or 'n/a'}",
                        task_name=task_name,
                    )
                    return actual_text

                async def _submit_price_filter(min_input, max_input, attempt: int):
                    # 首次优先“确定”按钮；无按钮时直接对输入框回车/失焦触发
                    if attempt == 1:
                        confirm_btn = price_container.get_by_text("确定", exact=True).first
                        if await confirm_btn.count() > 0 and await confirm_btn.is_visible():
                            await confirm_btn.click(timeout=3000)
                            return
                        target = max_input if has_max_price else min_input
                        await target.press("Enter", timeout=3000)
                        return
                    if attempt == 2:
                        target = max_input if has_max_price else min_input
                        await target.press("Enter", timeout=3000)
                        return
                    await page.keyboard.press("Tab")
                    await random_sleep(0.3, 0.8)
                    await page.keyboard.press("Enter")

                for attempt in range(1, max_price_retry + 1):
                    min_input = None
                    max_input = None
                    try:
                        panel_visible = await _open_price_filter_panel()
                        if not panel_visible:
                            log_time(
                                f"价格筛选第{attempt}/{max_price_retry}次：未展开价格输入面板。",
                                task_name=task_name,
                            )
                            await random_sleep(1, 2)
                            continue

                        min_input, max_input = await _resolve_price_inputs()
                        if min_input is None or max_input is None:
                            log_time(
                                f"价格筛选第{attempt}/{max_price_retry}次：未找到可编辑价格输入框。",
                                task_name=task_name,
                            )
                            await random_sleep(1, 2)
                            continue

                        # 关键修复：响应监听提前覆盖“填值+提交”全链路，避免漏抓fill触发的请求
                        async with page.expect_response(lambda r: API_URL_PATTERN in r.url, timeout=12000) as response_info:
                            if has_min_price:
                                await _fill_price_input(min_input, min_price, "最低价")
                            if has_max_price:
                                await _fill_price_input(max_input, max_price, "最高价")
                            await _submit_price_filter(min_input, max_input, attempt)
                            await random_sleep(1.2, 2.5)
                        final_response = await response_info.value
                        if final_response and final_response.ok:
                            price_filter_applied = True
                            log_time(
                                f"价格筛选提交成功（第{attempt}/{max_price_retry}次）。",
                                task_name=task_name,
                            )
                            break
                        log_time(
                            f"价格筛选第{attempt}/{max_price_retry}次提交完成但响应异常，准备重试。",
                            task_name=task_name,
                        )
                    except PlaywrightTimeoutError:
                        try:
                            min_actual = await min_input.input_value() if min_input is not None else "n/a"
                        except Exception:
                            min_actual = "n/a"
                        try:
                            max_actual = await max_input.input_value() if max_input is not None else "n/a"
                        except Exception:
                            max_actual = "n/a"
                        log_time(
                            f"价格筛选第{attempt}/{max_price_retry}次超时，准备重试。min_actual={min_actual} max_actual={max_actual}",
                            task_name=task_name,
                        )
                    except Exception as e:
                        log_time(
                            f"价格筛选第{attempt}/{max_price_retry}次失败：{e}",
                            task_name=task_name,
                        )

                if not price_filter_applied:
                    log_time("价格筛选已达到最大重试次数，降级继续执行后续流程。", task_name=task_name)

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
                f"price_sort_order={price_sort_order} | "
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

                    dedup_item_id = build_result_dedup_item_id({"商品信息": item_data})
                    if use_storage_dedup:
                        if not dedup_item_id:
                            log_time(
                                f"[页内进度 {i}/{total_items_on_page}] 商品缺少可用去重键，跳过：{item_data.get('商品标题', '')[:20]}...",
                                task_name=task_name,
                                level="warning",
                            )
                            continue
                        try:
                            if owner_storage.result_exists(dedup_item_id, owner_id=owner_id, task_name=task_name):
                                processed_links.add(unique_key)
                                log_time(
                                    f"[页内进度 {i}/{total_items_on_page}] 商品命中数据库去重，跳过：{item_data['商品标题'][:20]}...",
                                    task_name=task_name,
                                )
                                continue
                        except Exception as e:
                            log_time(f"数据库预去重检查失败，继续处理详情: {e}", task_name=task_name, level="warning")

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

                            # 1. 提取该商品的完整图片列表
                            image_infos = await safe_get(item_do, 'imageInfos', default=[])
                            if image_infos:
                                # 使用列表推导式获取所有有效的图片URL
                                all_image_urls = [img.get('url') for img in image_infos if img.get('url')]
                                if all_image_urls:
                                    # 用新的字段存储图片列表，替换掉旧的单个链接
                                    item_data['商品图片列表'] = all_image_urls
                                    # (可选) 仍然保留主图链接，以防万一
                                    item_data['商品主图链接'] = all_image_urls[0]

                            # 2. 提取“已用年限”（优先结构化字段，兜底标签拼接）
                            used_years = ""
                            cpv_labels = await safe_get(item_do, 'cpvLabels', default=[])
                            if isinstance(cpv_labels, list):
                                for label in cpv_labels:
                                    if not isinstance(label, dict):
                                        continue
                                    if label.get('propertyName') == "已用年限":
                                        used_years = (label.get('valueName') or '').strip()
                                        break
                            if not used_years:
                                item_label_ext_list = await safe_get(item_do, 'itemLabelExtList', default=[])
                                if isinstance(item_label_ext_list, list):
                                    for label in item_label_ext_list:
                                        if not isinstance(label, dict):
                                            continue
                                        props = str(label.get('properties') or '')
                                        if "已用年限:" in props:
                                            used_years = props.split("已用年限:", 1)[1].split("##", 1)[0].strip()
                                            break
                            if used_years:
                                item_data['已用年限'] = used_years

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
                            seller_credit_level_text = user_profile_data.get('卖家信用等级')
                            if not seller_credit_level_text:
                                seller_credit_level_text = await safe_get(seller_do, 'zhimaLevelInfo', 'levelName')
                                if seller_credit_level_text:
                                    user_profile_data['卖家信用等级'] = seller_credit_level_text
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
                                "price_sort_order": price_sort_order,
                                "region": region_filter or None,
                                "商品信息": item_data,
                                "卖家信息": user_profile_data
                            }

                            # 当前任务使用的Bayes版本，供预计算与推荐度融合统一使用
                            bayes_profile = task_config.get("bayes_profile", "bayes_v1")

                            # Bayes先验预计算，供后续AI分析使用（失败不影响主流程）
                            try:
                                bayes_precalc = build_bayes_precalc(
                                    final_record,
                                    bayes_profile,
                                    owner_id=owner_id,
                                )
                                if bayes_precalc:
                                    final_record["ml_precalc"] = {"bayes": bayes_precalc}
                            except Exception as e:
                                log_time(f"Bayes预计算失败: {e}", task_name=task_name)

                            # --- START: 实时AI分析和通知 ---
                            should_notify = False
                            notify_item_data = item_data
                            notify_reason = "无"
                            ai_analysis_result = None

                            # 检查是否跳过AI分析
                            if SKIP_AI_ANALYSIS():
                                log_time("环境变量 SKIP_AI_ANALYSIS 已设置，跳过AI分析。", task_name=task_name)
                                # 跳过AI分析时不需要下载图片，避免无意义的IO开销
                                downloaded_image_paths = []
                                should_notify = True
                                notify_reason = "商品已跳过AI分析，直接通知"
                            else:
                                current_item_id = item_data.get("商品ID", "未知ID")
                                log_time(f"开始对商品 #{current_item_id} 进行实时AI分析...", task_name=task_name)
                                
                                # 方案2：不再注入image_url/base64，避免为多模态下载冗余图片
                                downloaded_image_paths = []

                                # 2. 获取AI分析
                                if ai_prompt_text:
                                    try:
                                        # 注意：这里我们将整个记录传给AI，让它拥有最全的上下文
                                        ai_analysis_result = await get_ai_analysis(
                                            final_record,
                                            downloaded_image_paths,
                                            prompt_text=ai_prompt_text,
                                            owner_id=owner_id,
                                            bayes_profile=bayes_profile,
                                        )
                                        if ai_analysis_result:
                                            final_record['ai_analysis'] = ai_analysis_result
                                            level = ai_analysis_result.get("recommendation_level", "未知")
                                            score = ai_analysis_result.get("confidence_score")
                                            score_text = f"{float(score):.2f}" if isinstance(score, (int, float)) else "未知"
                                            recommended_flag = _is_ai_recommended(ai_analysis_result)
                                            log_time(
                                                f"AI分析完成。推荐等级: {level}，置信度: {score_text}，是否推荐: {recommended_flag}",
                                                task_name=task_name,
                                            )
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
                                        await notifier.send_task_completion_notification(
                                            task_name,
                                            f"AI调用失败-结束原因：{e}",
                                            processed_item_count,
                                            recommended_item_count,
                                            owner_id=owner_id,
                                            bound_task=task_name,
                                            bound_account=bound_account,
                                        )
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

                                # 3. 标记推荐商品，后续仅在落库成功时通知
                                if _is_ai_recommended(ai_analysis_result):
                                    should_notify = True
                                    item_data_with_analysis = item_data.copy()
                                    item_data_with_analysis['ai_analysis'] = ai_analysis_result
                                    notify_item_data = item_data_with_analysis
                                    notify_reason = ai_analysis_result.get("reason", "无")
                            # --- END: 实时AI分析和通知 ---

                            # 4. 先幂等保存，保存成功且首次创建才允许通知
                            save_meta = await save_to_jsonl(final_record, keyword, return_meta=True)
                            if not save_meta.get("saved"):
                                log_time("结果保存失败，跳过通知并继续后续流程。", task_name=task_name, level="warning")
                                continue

                            if not save_meta.get("created"):
                                processed_links.add(unique_key)
                                log_time("结果命中去重（并发或历史数据），本次不通知。", task_name=task_name)
                                continue

                            if should_notify:
                                log_time("结果首次入库且满足通知条件，开始发送通知。", task_name=task_name)
                                await send_all_notifications(
                                    notify_item_data,
                                    notify_reason,
                                    owner_id=owner_id,
                                    bound_task=task_name,
                                    bound_account=bound_account,
                                )

                            processed_links.add(unique_key)
                            processed_item_count += 1
                            # 首次入库且满足推荐/跳过AI直推时才增加推荐计数
                            if should_notify:
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

        except PriceSortApplyError as e:
            print(f"\n价格排序严格校验失败: {e.code} - {e}")
            end_reason = f"操作终止-结束原因：{e.code}:{e}"
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



