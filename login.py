import asyncio
import os
import json
from datetime import datetime
from typing import Dict, Any

from playwright.async_api import async_playwright

LOGIN_IS_EDGE = os.getenv("LOGIN_IS_EDGE", "false").lower() == "true"
RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "false").lower() == "true"
STATE_DIR = "state"

# 统一日志格式化函数
def log_message(task_name, level, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{task_name}] [{level.upper()}] {message}"

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
    async with async_playwright() as p:
        print(log_message("系统", "info", "正在启动自动登录程序..."))
        
        # 配置浏览器启动选项
        launch_options = {
            "headless": False,
            "args": ["--disable-web-security", "--allow-running-insecure-content"]
        }
        
        if LOGIN_IS_EDGE:
            browser = await p.chromium.launch(channel="msedge", **launch_options)
        else:
            if RUNNING_IN_DOCKER:
                browser = await p.chromium.launch(**launch_options)
            else:
                browser = await p.chromium.launch(channel="chrome", **launch_options)

        # 使用桌面版浏览器上下文（与旧版 login.py 相同）
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print(log_message("系统", "info", "正在打开咸鱼首页..."))
            await page.goto("https://www.goofish.com/")
            print(log_message("系统", "info", "等待页面加载完成..."))
            
            # 等待登录按钮出现并点击
            await page.wait_for_selector("div.nick--RyNYtDXM", timeout=60000)
            await page.click("div.nick--RyNYtDXM")
            print(log_message("系统", "info", "已点击登录按钮"))

            # 等待登录完成 - 这里我们监听页面变化，当登录iframe消失时认为登录完成
            print("\n" + "=" * 50)
            print("自动登录程序已启动，请在打开的浏览器窗口中登录您的咸鱼账号。")
            print("推荐使用APP扫码登录。")
            print("登录成功后，登录窗口将自动消失，无需手动关闭。")
            print("=" * 50 + "\n")

            try:
                # 将chrome的cookie sameSite值映射为Playwright兼容的值
                def map_same_site_value(chrome_same_site):
                    # Chrome对于没有SameSite属性的cookie返回None
                    if chrome_same_site is None:
                        return "Lax"  # 未指定cookie的默认值
                    
                    # 将Playwright的sameSite值映射为与chrome插件一致的格式
                    same_site_map = {
                        "none": "None",
                        "lax": "Lax",
                        "strict": "Strict"
                    }
                    
                    return same_site_map.get(chrome_same_site.lower(), "Lax")

                # 更可靠的登录检测机制：
                # 1. 等待登录iframe消失
                # 2. 访问个人页面
                # 3. 检查是否再次弹出登录iframe，如果没有则登录成功
                print(log_message("系统", "info", "正在等待登录完成..."))
                
                login_successful = False
                timeout_reached = False
                
                # 最多等待300秒完成登录
                for total_attempt in range(600):  # 300秒 / 0.5秒间隔
                    # 检查登录iframe是否消失
                    try:
                        # 等待iframe出现或等待1秒
                        await page.wait_for_selector("#alibaba-login-box", timeout=1000)
                    except:
                        # iframe消失了，尝试验证登录状态
                        print(log_message("系统", "info", "检测到登录iframe消失，正在验证登录状态..."))
                        
                        try:
                            # 刷新当前页面而不是访问个人页面，避免404错误
                            await page.reload(timeout=10000)
                            print(log_message("系统", "info", "已刷新页面，正在检查登录状态..."))
                            
                            # 检查是否再次弹出登录iframe或页面上是否有登录相关元素
                            login_incomplete = False
                            
                            # 检查登录iframe是否出现
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
                                print(log_message("系统", "warning", "页面仍需要登录，登录未完成"))
                                # 可能需要点击登录按钮重新触发登录流程
                                try:
                                    await page.click("div.nick--RyNYtDXM", timeout=5000)
                                    print(log_message("系统", "info", "已重新点击登录按钮"))
                                except:
                                    pass
                            else:
                                # 登录iframe和登录元素都没有出现，登录成功
                                print(log_message("系统", "info", "页面已登录，登录成功"))
                                
                                # 从真实浏览器环境中抓取信息
                                print(log_message("系统", "info", "正在抓取浏览器环境信息..."))
                                browser_env = await page.evaluate('''() => {
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
                                
                                print(log_message("系统", "info", "浏览器环境信息抓取成功"))
                                
                                # 保存登录状态并处理成标准格式
                                full_state = await context.storage_state()
                                
                                # 提取所有与goofish.com相关的cookie
                                filtered_cookies = []
                                for cookie in full_state.get("cookies", []):
                                    if "goofish.com" in cookie.get("domain", ""):
                                        filtered_cookies.append(cookie)
                                
                                standard_cookies = []
                                for cookie in filtered_cookies:
                                    clean_cookie = {
                                        "name": cookie["name"],
                                        "value": cookie["value"],
                                        "domain": cookie["domain"],
                                        "path": cookie["path"],
                                        "expires": cookie["expires"],
                                        "httpOnly": cookie["httpOnly"],
                                        "secure": cookie["secure"],
                                        "sameSite": map_same_site_value(cookie.get("sameSite"))
                                    }
                                    standard_cookies.append(clean_cookie)
                                
                                # 创建增强版快照格式
                                snapshot_data = {
                                    "capturedAt": datetime.now().isoformat(),
                                    "pageUrl": page.url,
                                    "page": {
                                        "pageUrl": page.url,
                                        "referrer": page.url,  # 使用当前页面作为referrer
                                        "visibilityState": "visible"
                                    },
                                    "env": browser_env,
                                    "storage": browser_env["storage"],
                                    "meta": {
                                        "droppedStorageKeys": {
                                            "local": [],
                                            "session": []
                                        }
                                    },
                                    "headers": {
                                        "User-Agent": browser_env["navigator"]["userAgent"],
                                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                                        "Accept-Language": browser_env["navigator"]["language"],
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
                                    },
                                    "cookies": standard_cookies
                                }
                                
                                # 生成唯一账号名称并保存到state目录
                                ensure_state_dir()
                                account_name = generate_unique_account_name()
                                display_name = f"自动获取账号_{datetime.now().strftime('%m%d_%H%M')}"
                                account_data = {
                                    "display_name": display_name,
                                    "created_at": datetime.now().isoformat(),
                                    "last_used_at": None,
                                    "risk_control_count": 0,
                                    "risk_control_history": [],
                                    "cookies": snapshot_data["cookies"],
                                    "env": snapshot_data.get("env"),
                                    "headers": snapshot_data.get("headers"),
                                    "page": snapshot_data.get("page"),
                                    "storage": snapshot_data.get("storage")
                                }
                                
                                account_file_path = os.path.join(STATE_DIR, f"{account_name}.json")
                                with open(account_file_path, 'w', encoding='utf-8') as f:
                                    json.dump(account_data, f, indent=2, ensure_ascii=False)
                                print(log_message("系统", "info", f"登录状态已成功保存到: {account_file_path}"))
                                
                                # 验证保存的状态文件
                                if os.path.exists(account_file_path):
                                    with open(account_file_path, 'r', encoding='utf-8') as f:
                                        state_data = json.load(f)
                                    if state_data.get('cookies') and len(state_data['cookies']) > 0:
                                        print(log_message("系统", "info", f"已保存 {len(state_data['cookies'])} 个Cookie"))
                                    else:
                                        print(log_message("系统", "warning", "保存的状态文件中Cookie数量为0，请检查登录状态"))
                                
                                login_successful = True
                                break
                                
                        except Exception as e:
                            print(log_message("系统", "error", f"验证登录状态时出错: {e}"))
                
                    if login_successful:
                        break
                        
                    await page.wait_for_timeout(500)  # 等待500毫秒后再检查
                
                if not login_successful:
                    print(log_message("系统", "warning", "登录超时，未成功完成登录"))
                    print(log_message("系统", "info", "正在尝试最后一次保存状态..."))
                    
                    # 尝试手动保存状态
                    full_state = await context.storage_state()
                    
                    filtered_cookies = []
                    for cookie in full_state.get("cookies", []):
                        if "goofish.com" in cookie.get("domain", ""):
                            clean_cookie = {
                                "name": cookie["name"],
                                "value": cookie["value"],
                                "domain": cookie["domain"],
                                "path": cookie["path"],
                                "expires": cookie["expires"],
                                "httpOnly": cookie["httpOnly"],
                                "secure": cookie["secure"],
                                "sameSite": map_same_site_value(cookie.get("sameSite"))
                            }
                            filtered_cookies.append(clean_cookie)
                    
                    # 生成唯一账号名称并保存到state目录
                    ensure_state_dir()
                    account_name = generate_unique_account_name()
                    display_name = f"自动获取账号_{datetime.now().strftime('%m%d_%H%M')}"
                    account_data = {
                        "display_name": display_name,
                        "created_at": datetime.now().isoformat(),
                        "last_used_at": None,
                        "risk_control_count": 0,
                        "risk_control_history": [],
                        "cookies": filtered_cookies
                    }
                    
                    account_file_path = os.path.join(STATE_DIR, f"{account_name}.json")
                    with open(account_file_path, 'w', encoding='utf-8') as f:
                        json.dump(account_data, f, indent=2, ensure_ascii=False)
                    print(log_message("系统", "info", f"登录状态已手动保存到: {account_file_path}"))
                
            except Exception as e:
                print(log_message("系统", "warning", f"登录过程出错: {e}"))
                print(log_message("系统", "info", "正在尝试手动保存状态..."))
                
                # 尝试手动保存状态
                try:
                    full_state = await context.storage_state()
                    
                    def map_same_site_value(chrome_same_site):
                        if chrome_same_site is None:
                            return "Lax"
                        
                        same_site_map = {
                            "none": "None",
                            "lax": "Lax",
                            "strict": "Strict"
                        }
                        
                        return same_site_map.get(chrome_same_site.lower(), "Lax")
                    
                    # 获取所有与goofish.com相关的cookie
                    filtered_cookies = []
                    for cookie in full_state.get("cookies", []):
                        if "goofish.com" in cookie.get("domain", ""):
                            clean_cookie = {
                                "name": cookie["name"],
                                "value": cookie["value"],
                                "domain": cookie["domain"],
                                "path": cookie["path"],
                                "expires": cookie["expires"],
                                "httpOnly": cookie["httpOnly"],
                                "secure": cookie["secure"],
                                "sameSite": map_same_site_value(cookie.get("sameSite"))
                            }
                            filtered_cookies.append(clean_cookie)
                    
                    # 生成唯一账号名称并保存到state目录
                    ensure_state_dir()
                    account_name = generate_unique_account_name()
                    display_name = f"自动获取账号_{datetime.now().strftime('%m%d_%H%M')}"
                    account_data = {
                        "display_name": display_name,
                        "created_at": datetime.now().isoformat(),
                        "last_used_at": None,
                        "risk_control_count": 0,
                        "risk_control_history": [],
                        "cookies": filtered_cookies
                    }
                    
                    account_file_path = os.path.join(STATE_DIR, f"{account_name}.json")
                    with open(account_file_path, 'w', encoding='utf-8') as f:
                        json.dump(account_data, f, indent=2, ensure_ascii=False)
                    print(log_message("系统", "info", f"登录状态已手动保存到: {account_file_path}"))
                except Exception as save_error:
                    print(log_message("系统", "error", f"手动保存状态失败: {save_error}"))
                    
        except Exception as e:
            print(log_message("系统", "error", f"页面加载或登录流程出错: {e}"))
        finally:
            # 关闭浏览器
            await browser.close()

            # 确保不生成 xianyu_state.json 文件
            if os.path.exists("xianyu_state.json"):
                try:
                    os.remove("xianyu_state.json")
                    print(log_message("系统", "info", "已删除临时文件 xianyu_state.json"))
                except Exception as e:
                    print(log_message("系统", "warning", f"删除临时文件失败: {e}"))


if __name__ == "__main__":
    print(log_message("系统", "info", "正在启动咸鱼登录流程..."))
    asyncio.run(main())
