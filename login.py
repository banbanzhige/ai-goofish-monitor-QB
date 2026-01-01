import asyncio
import os
from playwright.async_api import async_playwright
import json

STATE_FILE = "xianyu_state.json"
LOGIN_IS_EDGE = os.getenv("LOGIN_IS_EDGE", "false").lower() == "true"
RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "false").lower() == "true"


async def main():
    async with async_playwright() as p:
        print("正在启动自动登录程序...")
        
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

        # 创建一个新的浏览器上下文
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("正在打开咸鱼首页...")
            await page.goto("https://www.goofish.com/")
            print("等待页面加载完成...")
            
            # 等待登录按钮出现并点击
            await page.wait_for_selector("div.nick--RyNYtDXM", timeout=60000)
            await page.click("div.nick--RyNYtDXM")
            print("已点击登录按钮")

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
                print("正在等待登录完成...")
                
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
                        print("检测到登录iframe消失，正在验证登录状态...")
                        
                        try:
                            # 刷新当前页面而不是访问个人页面，避免404错误
                            await page.reload(timeout=10000)
                            print("已刷新页面，正在检查登录状态...")
                            
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
                                print("⚠️ 页面仍需要登录，登录未完成")
                                # 可能需要点击登录按钮重新触发登录流程
                                try:
                                    await page.click("div.nick--RyNYtDXM", timeout=5000)
                                    print("已重新点击登录按钮")
                                except:
                                    pass
                            else:
                                # 登录iframe和登录元素都没有出现，登录成功
                                print("✅ 页面已登录，登录成功")
                                
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
                                
                                standard_state = {"cookies": standard_cookies}
                                
                                # 写入文件
                                with open(STATE_FILE, 'w', encoding='utf-8') as f:
                                    json.dump(standard_state, f, indent=2, ensure_ascii=False)
                                print(f"✅ 登录状态已成功保存到: {STATE_FILE}")
                                
                                # 验证保存的状态文件
                                if os.path.exists(STATE_FILE):
                                    with open(STATE_FILE, 'r', encoding='utf-8') as f:
                                        state_data = json.load(f)
                                    if state_data.get('cookies') and len(state_data['cookies']) > 0:
                                        print(f"✅ 已保存 {len(state_data['cookies'])} 个Cookie")
                                    else:
                                        print("⚠️ 保存的状态文件中Cookie数量为0，请检查登录状态")
                                
                                login_successful = True
                                break
                                
                        except Exception as e:
                            print(f"验证登录状态时出错: {e}")
                
                    if login_successful:
                        break
                        
                    await page.wait_for_timeout(500)  # 等待500毫秒后再检查
                
                if not login_successful:
                    print("⚠️ 登录超时，未成功完成登录")
                    print("正在尝试最后一次保存状态...")
                    
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
                    
                    standard_state = {"cookies": filtered_cookies}
                    with open(STATE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(standard_state, f, indent=2, ensure_ascii=False)
                    print(f"✅ 登录状态已手动保存到: {STATE_FILE}")
                
            except Exception as e:
                print(f"⚠️ 登录过程出错: {e}")
                print("正在尝试手动保存状态...")
                
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
                    
                    standard_state = {"cookies": filtered_cookies}
                    with open(STATE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(standard_state, f, indent=2, ensure_ascii=False)
                    print(f"✅ 登录状态已手动保存到: {STATE_FILE}")
                except Exception as save_error:
                    print(f"❌ 手动保存状态失败: {save_error}")
                    
        except Exception as e:
            print(f"❌ 页面加载或登录流程出错: {e}")
        finally:
            # 关闭浏览器
            await browser.close()


if __name__ == "__main__":
    print("正在启动咸鱼登录流程...")
    asyncio.run(main())
