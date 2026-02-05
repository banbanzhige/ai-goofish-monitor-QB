import asyncio
import os
import json
from datetime import datetime

from playwright.async_api import async_playwright
from src.logging_config import setup_logging, get_logger

STATE_DIR = "state"
COOKIE_ALLOWED_DOMAINS = ("goofish.com",)
LOGIN_COOKIE_NAMES = {"_m_h5_tk", "cookie2", "sgcookie"}

logger = get_logger(__name__, service="system")

def _setup_logging_from_config():
    from src.config import (
        LOG_LEVEL,
        LOG_CONSOLE_LEVEL,
        LOG_DIR,
        LOG_MAX_BYTES,
        LOG_BACKUP_COUNT,
        LOG_RETENTION_DAYS,
        LOG_JSON_FORMAT,
        LOG_ENABLE_LEGACY
    )
    setup_logging(
        log_dir=LOG_DIR(),
        log_level=LOG_LEVEL(),
        console_level=LOG_CONSOLE_LEVEL(),
        max_bytes=LOG_MAX_BYTES(),
        backup_count=LOG_BACKUP_COUNT(),
        retention_days=LOG_RETENTION_DAYS(),
        enable_json=LOG_JSON_FORMAT(),
        enable_legacy=LOG_ENABLE_LEGACY()
    )

def _get_runtime_flags():
    from src.config import (
        LOGIN_IS_EDGE as CONFIG_LOGIN_IS_EDGE,
        RUNNING_IN_DOCKER as CONFIG_RUNNING_IN_DOCKER
    )
    return CONFIG_LOGIN_IS_EDGE(), CONFIG_RUNNING_IN_DOCKER()

def _default_context_options() -> dict:
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
    """过滤并标准化登录态Cookie，避免写入无关数据。"""
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

def _has_login_cookies(cookies: list) -> bool:
    """判断是否已拿到关键登录Cookie。"""
    if not cookies:
        return False
    names = {cookie.get("name") for cookie in cookies if cookie.get("name")}
    return bool(LOGIN_COOKIE_NAMES & names)

def _build_account_payload(snapshot_data: dict, display_name: str) -> dict:
    """组装账号信息文件内容。"""
    return {
        "display_name": display_name,
        "created_at": datetime.now().isoformat(),
        "last_used_at": None,
        "risk_control_count": 0,
        "risk_control_history": [],
        "cookies": snapshot_data.get("cookies", []),
        "env": snapshot_data.get("env"),
        "headers": snapshot_data.get("headers"),
        "page": snapshot_data.get("page"),
        "storage": snapshot_data.get("storage")
    }

def _save_account_file(account_data: dict) -> str:
    """保存账号文件并返回保存路径。"""
    ensure_state_dir()
    account_name = generate_unique_account_name()
    account_file_path = os.path.join(STATE_DIR, f"{account_name}.json")
    with open(account_file_path, 'w', encoding='utf-8') as f:
        json.dump(account_data, f, indent=2, ensure_ascii=False)
    return account_file_path

async def _build_snapshot(context, page) -> dict:
    """构建登录状态快照。"""
    full_state = await context.storage_state()
    standard_cookies = _filter_cookies_for_state(full_state.get("cookies", []))
    browser_env = await _capture_browser_env(page)
    headers = _build_snapshot_headers(browser_env)
    return {
        "capturedAt": datetime.now().isoformat(),
        "pageUrl": page.url,
        "page": {
            "pageUrl": page.url,
            "referrer": page.url,
            "visibilityState": "visible"
        },
        "env": browser_env,
        "storage": (browser_env or {}).get("storage", {}),
        "meta": {
            "droppedStorageKeys": {
                "local": [],
                "session": []
            }
        },
        "headers": headers,
        "cookies": standard_cookies
    }

async def _navigate_and_stabilize(page, target_url: str = "https://www.goofish.com/personal") -> None:
    """登录成功后跳转个人页并等待页面稳定，以提升 Cookie 完整性。"""
    try:
        logger.info(
            "登录成功后准备跳转个人页...",
            extra={"event": "login_profile_navigate_start", "target_url": target_url}
        )
        await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            await page.wait_for_timeout(2000)
        logger.info(
            "个人页加载完成，等待页面稳定...",
            extra={"event": "login_profile_loaded"}
        )
    except Exception as e:
        logger.warning(
            "跳转个人页失败，改为刷新当前页等待稳定",
            extra={"event": "login_profile_navigate_failed", "error": str(e)},
            exc_info=True
        )
        try:
            await page.reload(timeout=15000, wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
        except Exception as reload_error:
            logger.warning(
                "刷新等待稳定失败，继续尝试保存",
                extra={"event": "login_profile_reload_failed", "error": str(reload_error)},
                exc_info=True
            )
    await page.wait_for_timeout(3000)
    logger.info(
        "登录后页面已稳定，准备保存Cookie",
        extra={"event": "login_profile_stabilized"}
    )

async def _capture_browser_env(page):
    """抓取浏览器环境快照，失败时返回空对象。"""
    try:
        return await page.evaluate('''() => {
            // 从浏览器中获取真实的环境信息
            const intl = (() => {
                try {
                    return Intl.DateTimeFormat().resolvedOptions();
                } catch (e) {
                    return {};
                }
            })();

            const uaData = (() => {
                try {
                    return navigator.userAgentData ? navigator.userAgentData.toJSON() : null;
                } catch (e) {
                    return null;
                }
            })();

            // 过滤存储数据，只保留简单的数据类型，避免保存复杂的 JavaScript 代码
            const filterStorageData = (storage) => {
                const filtered = {};
                for (let i = 0; i < storage.length; i += 1) {
                    const key = storage.key(i);
                    if (key !== null) {
                        try {
                            const value = storage.getItem(key);
                            // 过滤掉包含大量 JavaScript 代码的项
                            if (value && typeof value === 'string') {
                                // 检查值的大小，过滤掉过大的内容
                                if (value.length > 1000) {
                                    continue;
                                }
                                // 检查是否包含 JavaScript 代码特征
                                const hasJsCode = value.includes('function') || value.includes('{') && value.includes('}') && value.includes(';') || value.includes('return');
                                if (hasJsCode) {
                                    continue;
                                }
                            }
                            filtered[key] = value;
                        } catch (e) {
                            continue;
                        }
                    }
                }
                return filtered;
            };

            return {
                navigator: {
                    userAgent: navigator.userAgent,
                    platform: navigator.platform,
                    vendor: navigator.vendor,
                    language: navigator.language,
                    languages: navigator.languages,
                    hardwareConcurrency: navigator.hardwareConcurrency,
                    deviceMemory: navigator.deviceMemory,
                    webdriver: navigator.webdriver,
                    doNotTrack: navigator.doNotTrack,
                    maxTouchPoints: navigator.maxTouchPoints,
                    userAgentData: uaData,
                },
                screen: {
                    width: screen.width,
                    height: screen.height,
                    availWidth: screen.availWidth,
                    availHeight: screen.availHeight,
                    colorDepth: screen.colorDepth,
                    pixelDepth: screen.pixelDepth,
                    devicePixelRatio: window.devicePixelRatio,
                },
                intl,
                storage: {
                    local: (() => {
                        try {
                            return filterStorageData(localStorage);
                        } catch (e) {
                            return {};
                        }
                    })(),
                    session: (() => {
                        try {
                            return filterStorageData(sessionStorage);
                        } catch (e) {
                            return {};
                        }
                    })(),
                },
            };
        }''')
    except Exception:
        return {}

def _build_snapshot_headers(browser_env: dict) -> dict:
    """基于环境快照构造请求头，便于后续复用。"""
    navigator = (browser_env or {}).get("navigator") or {}
    headers = {
        "User-Agent": navigator.get("userAgent", ""),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": navigator.get("language", ""),
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.goofish.com/",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": '"Android"',
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    }
    return {key: value for key, value in headers.items() if value}


def ensure_state_dir():
    """确保state目录存在"""
    os.makedirs(STATE_DIR, exist_ok=True)

def generate_unique_account_name():
    """生成唯一的账号名称"""
    ensure_state_dir()
    base_name = "auto_account"
    counter = 1
    while True:
        account_name = f"{base_name}_{counter}"
        if not os.path.exists(os.path.join(STATE_DIR, f"{account_name}.json")):
            return account_name
        counter += 1

async def main():
    _setup_logging_from_config()
    login_is_edge, running_in_docker = _get_runtime_flags()

    async with async_playwright() as p:
        logger.info("正在启动自动登录程序...", extra={"event": "login_start"})
        logger.info(
            "登录配置已加载",
            extra={
                "event": "login_config_loaded",
                "login_is_edge": login_is_edge,
                "running_in_docker": running_in_docker
            }
        )

        # 配置浏览器启动选项
        launch_options = {
            "headless": False,
            "args": ["--disable-web-security", "--allow-running-insecure-content"]
        }

        if login_is_edge:
            browser = await p.chromium.launch(channel="msedge", **launch_options)
        else:
            if running_in_docker:
                browser = await p.chromium.launch(**launch_options)
            else:
                browser = await p.chromium.launch(channel="chrome", **launch_options)

        # 使用桌面版浏览器上下文（与旧版 login.py 相同）
        context = await browser.new_context(**_default_context_options())
        page = await context.new_page()

        try:
            logger.info("正在打开咸鱼首页...", extra={"event": "login_open_home"})
            await page.goto("https://www.goofish.com/")
            logger.info("等待页面加载完成...", extra={"event": "login_wait_page"})

            # 等待登录按钮出现并点击
            await page.wait_for_selector("div.nick--RyNYtDXM", timeout=60000)
            await page.click("div.nick--RyNYtDXM")
            logger.info("已点击登录按钮", extra={"event": "login_click_button"})

            # 等待登录完成 - 这里我们监听页面变化，当登录iframe消失时认为登录完成
            logger.info("=" * 50, extra={"event": "login_prompt"})
            logger.info(
                "自动登录程序已启动，请在打开的浏览器窗口中登录您的咸鱼账号。\n"
                "推荐使用APP扫码登录。\n"
                "登录成功后，登录窗口将自动消失，无需手动关闭。",
                extra={"event": "login_prompt"}
            )
            logger.info("=" * 50, extra={"event": "login_prompt"})

            try:
                # 将Chrome的cookie sameSite值映射为Playwright兼容的值
                def map_same_site_value(chrome_same_site):
                    # Chrome对于没有SameSite属性的cookie返回None
                    if chrome_same_site is None:
                        return "Lax"  # 未指定cookie的默认值

                    # 将Playwright的sameSite值映射为与Chrome插件一致的格式
                    same_site_map = {
                        "none": "None",
                        "lax": "Lax",
                        "strict": "Strict"
                    }

                    return same_site_map.get(chrome_same_site.lower(), "Lax")

                # 更可靠的登录检测机制：
                # 1. 等待登录iframe消失
                # 2. 访问个人页面
                # 3. 检查是否再次弹出登录frame，如果没有则登录成功
                logger.info("正在等待登录完成...", extra={"event": "login_waiting"})

                login_successful = False

                # 最多等待300秒完成登录
                for total_attempt in range(600):  # 300秒 / 0.5秒间隔
                    # 每2秒检测一次关键cookie，避免依赖页面元素变化
                    if total_attempt % 4 == 0:
                        try:
                            snapshot_data = await _build_snapshot(context, page)
                            if _has_login_cookies(snapshot_data.get("cookies", [])):
                                logger.info(
                                    "已检测到关键Cookie，等待4秒以获取更完整的状态...",
                                    extra={"event": "login_cookie_detected", "delay_seconds": 4}
                                )
                                await page.wait_for_timeout(4000)
                                await _navigate_and_stabilize(page)
                                snapshot_data = await _build_snapshot(context, page)
                                if not _has_login_cookies(snapshot_data.get("cookies", [])):
                                    logger.warning(
                                        "稳定后未检测到关键Cookie，继续等待登录完成",
                                        extra={"event": "login_cookie_missing_after_stable"}
                                    )
                                    continue
                                display_name = f"自动获取账号_{datetime.now().strftime('%m%d_%H%M')}"
                                account_data = _build_account_payload(snapshot_data, display_name)
                                account_file_path = _save_account_file(account_data)
                                logger.info(
                                    f"已检测到登录Cookie，延迟保存到: {account_file_path}",
                                    extra={
                                        "event": "login_cookie_saved",
                                        "account_file_path": account_file_path
                                    }
                                )
                                login_successful = True
                                break
                        except Exception as e:
                            logger.warning(
                                "检测登录Cookie失败",
                                extra={"event": "login_cookie_check_failed", "error": str(e)},
                                exc_info=True
                            )

                    # 检查登录frame是否消失
                    try:
                        # 等待iframe出现或等待1秒
                        await page.wait_for_selector("#alibaba-login-box", timeout=1000)
                    except:
                        # iframe消失了，尝试验证登录状态
                        logger.info(
                            "检测到登录iframe消失，正在验证登录状态...",
                            extra={"event": "login_iframe_gone"}
                        )

                        try:
                            # 刷新当前页面而不是访问个人页面，避免404错误
                            await page.reload(timeout=10000)
                            logger.info(
                                "已刷新页面，正在检查登录状态...",
                                extra={"event": "login_page_reloaded"}
                            )

                            # 检查是否再次弹出登录frame或页面上是否有登录相关元素
                            login_incomplete = False

                            # 检查登录frame是否出现
                            try:
                                await page.wait_for_selector("#alibaba-login-box", timeout=2000)
                                login_incomplete = True
                            except:
                                pass

                            # 如果iframe没出现，检查页面上的登录元素
                            if not login_incomplete:
                                # 在5秒内检查是否有登录按钮或立即登录悬浮框
                                found_login_elements = False
                                for i in range(10):  # 5秒 / 0.5秒间隔
                                    # 检查右上角的登录按钮是否存在
                                    try:
                                        await page.wait_for_selector("a[href*='login']", timeout=100)
                                        found_login_elements = True
                                        break
                                    except:
                                        pass

                                    # 检查页面下方的立即登录悬浮框是否存在
                                    try:
                                        await page.wait_for_selector("div[class*='login']", timeout=100)
                                        found_login_elements = True
                                        break
                                    except:
                                        pass

                                    await page.wait_for_timeout(500)  # 等待500毫秒后再检查

                                login_incomplete = found_login_elements

                            if login_incomplete:
                                logger.warning(
                                    "页面仍需要登录，登录未完成",
                                    extra={"event": "login_incomplete"}
                                )
                                # 可能需要点击登录按钮重新触发登录流程
                                try:
                                    await page.click("div.nick--RyNYtDXM", timeout=5000)
                                    logger.info(
                                        "已重新点击登录按钮",
                                        extra={"event": "login_reclick"}
                                    )
                                except:
                                    pass
                            else:
                                # 登录frame和登录元素都没有出现，登录成功
                                logger.info(
                                    "页面已登录，登录成功",
                                    extra={"event": "login_success"}
                                )

                                await _navigate_and_stabilize(page)
                                snapshot_data = await _build_snapshot(context, page)
                                if not _has_login_cookies(snapshot_data.get("cookies", [])):
                                    logger.warning(
                                        "页面显示已登录但关键Cookie缺失，继续等待",
                                        extra={"event": "login_cookie_missing_after_login"}
                                    )
                                    continue
                                display_name = f"自动获取账号_{datetime.now().strftime('%m%d_%H%M')}"
                                account_data = _build_account_payload(snapshot_data, display_name)
                                account_file_path = _save_account_file(account_data)
                                logger.info(
                                    f"登录状态已成功保存到: {account_file_path}",
                                    extra={
                                        "event": "login_state_saved",
                                        "account_file_path": account_file_path
                                    }
                                )

                                if account_data.get("cookies"):
                                    cookie_count = len(account_data["cookies"])
                                    logger.info(
                                        f"已保存 {cookie_count} 个Cookie",
                                        extra={
                                            "event": "login_cookie_count",
                                            "cookie_count": cookie_count
                                        }
                                    )
                                else:
                                    logger.warning(
                                        "保存的状态文件中Cookie数量为0，请检查登录状态",
                                        extra={"event": "login_cookie_empty"}
                                    )

                                login_successful = True
                                break

                        except Exception as e:
                            logger.error(
                                "验证登录状态时出错",
                                extra={"event": "login_state_verify_failed", "error": str(e)},
                                exc_info=True
                            )

                    if login_successful:
                        break

                    await page.wait_for_timeout(500)  # 等待500毫秒后再检查

                if not login_successful:
                    logger.warning(
                        "登录超时，未成功完成登录",
                        extra={"event": "login_timeout"}
                    )
                    logger.info(
                        "正在尝试最后一次保存状态...",
                        extra={"event": "login_save_last_attempt"}
                    )

                    snapshot_data = await _build_snapshot(context, page)
                    display_name = f"自动获取账号_{datetime.now().strftime('%m%d_%H%M')}"
                    account_data = _build_account_payload(snapshot_data, display_name)
                    account_file_path = _save_account_file(account_data)
                    logger.info(
                        f"登录状态已手动保存到: {account_file_path}",
                        extra={
                            "event": "login_state_saved_manual",
                            "account_file_path": account_file_path
                        }
                    )

            except Exception as e:
                logger.warning(
                    "登录过程出错",
                    extra={"event": "login_flow_error", "error": str(e)},
                    exc_info=True
                )
                logger.info(
                    "正在尝试手动保存状态...",
                    extra={"event": "login_save_manual_attempt"}
                )

                # 尝试手动保存状态
                try:
                    snapshot_data = await _build_snapshot(context, page)
                    display_name = f"自动获取账号_{datetime.now().strftime('%m%d_%H%M')}"
                    account_data = _build_account_payload(snapshot_data, display_name)
                    account_file_path = _save_account_file(account_data)
                    logger.info(
                        f"登录状态已手动保存到: {account_file_path}",
                        extra={
                            "event": "login_state_saved_manual",
                            "account_file_path": account_file_path
                        }
                    )
                except Exception as save_error:
                    logger.error(
                        "手动保存状态失败",
                        extra={"event": "login_save_manual_failed", "error": str(save_error)},
                        exc_info=True
                    )

        except Exception as e:
            logger.error(
                "页面加载或登录流程出错",
                extra={"event": "login_page_error", "error": str(e)},
                exc_info=True
            )
        finally:
            # 关闭浏览器
            await browser.close()

            # 确保不生成xianyu_state.json文件
            if os.path.exists("xianyu_state.json"):
                try:
                    os.remove("xianyu_state.json")
                    logger.info(
                        "已删除临时文件 xianyu_state.json",
                        extra={"event": "login_temp_state_removed"}
                    )
                except Exception as e:
                    logger.warning(
                        "删除临时文件失败",
                        extra={"event": "login_temp_state_remove_failed", "error": str(e)},
                        exc_info=True
                    )

if __name__ == "__main__":
    asyncio.run(main())
