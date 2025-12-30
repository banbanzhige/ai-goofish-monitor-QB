import asyncio
import os
from PIL import Image
import qrcode
from playwright.async_api import async_playwright
import pyzbar.pyzbar as pyzbar

STATE_FILE = "xianyu_state.json"
LOGIN_IS_EDGE = os.getenv("LOGIN_IS_EDGE", "false").lower() == "true"
RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "false").lower() == "true"


async def main():
    async with async_playwright() as p:
        print("正在启动浏览器...")
        if LOGIN_IS_EDGE:
            browser = await p.chromium.launch(headless=False, channel="msedge")
        else:
            if RUNNING_IN_DOCKER:
                browser = await p.chromium.launch(headless=False)
            else:
                browser = await p.chromium.launch(headless=False, channel="chrome")

        context = await browser.new_context()
        page = await context.new_page()

        print("正在打开咸鱼首页...")
        await page.goto("https://www.goofish.com/")
        print("等待登录按钮出现...")
        await page.wait_for_selector("div.nick--RyNYtDXM")
        await page.click("div.nick--RyNYtDXM")
        print("已点击登录按钮，等待iframe...")

        try:
            frame_element = await page.wait_for_selector(
                "#alibaba-login-box", timeout=60000
            )
            frame = await frame_element.content_frame()
            print("登录iframe加载完成")
        except Exception as e:
            print(f"iframe加载失败: {e}")
            return

        try:
            print("等待二维码 canvas 出现...")
            canvas_element = await frame.wait_for_selector(
                "#qrcode-img canvas", timeout=60000
            )
            print("二维码 canvas 加载完成，截图保存为 qrcode.png")
            await canvas_element.screenshot(path="qrcode.png")
        except Exception as e:
            print(f"二维码截图失败: {e}")
            return

        img = Image.open("qrcode.png")
        try:
            qr = pyzbar.decode(img)
            if qr:
                qr_data = qr[0].data.decode()
                print(f"已识别二维码内容：{qr_data}")
                qr_code = qrcode.QRCode(border=1)
                qr_code.add_data(qr_data)
                qr_code.make(fit=True)
                qr_code.print_ascii(invert=True)
            else:
                print("⚠️ 未识别到二维码内容，二维码已保存为 qrcode.png")
        except ImportError:
            print("未安装 pyzbar，二维码已保存为 qrcode.png")

        print("\n" + "=" * 50)
        print("请在打开的浏览器窗口中手动登录您的咸鱼账号。")
        print("推荐使用APP扫码登录。")
        print("登录成功后，回到这里，按 Enter 键继续...")
        print("=" * 50 + "\n")

        loop = asyncio.get_running_loop()
        # await loop.run_in_executor(None, input)

        print("等待登录完成...")

        try:
            print("检查是否有短信验证提示...")
            sms_tip = None
            selectors = [
                "#J_Form > div > div.ui-tiptext.ui-tiptext-message",
                "div.ui-tiptext.ui-tiptext-message",
                ".ui-tiptext.ui-tiptext-message",
            ]
            for selector in selectors:
                try:
                    sms_tip = await frame.wait_for_selector(selector, timeout=30000)
                    if sms_tip:
                        break
                except:
                    continue

            if sms_tip:
                tip_text = await sms_tip.text_content()
                print(f"检测到提示文本: {tip_text}")
                if "短信验证" in tip_text:
                    print("⚠️ 检测到需要短信验证码验证")

                    get_code_button = await frame.wait_for_selector(
                        "#J_GetCode", timeout=10000
                    )
                    print("点击获取验证码按钮...")
                    await get_code_button.click()
                    print("已点击获取验证码按钮")

                    await frame.wait_for_selector("#J_Checkcode", timeout=10000)
                    print("请输入收到的6位数字验证码：")
                    verification_code = await loop.run_in_executor(None, input)

                    verification_input = await frame.wait_for_selector(
                        "#J_Checkcode", timeout=10000
                    )
                    await verification_input.fill(verification_code)
                    print(f"已输入验证码: {verification_code}")

                    submit_button = await frame.wait_for_selector(
                        "#btn-submit", timeout=10000
                    )
                    await submit_button.click()
                    print("已点击提交按钮")

                    try:
                        keep_button = await frame.wait_for_selector(
                            "button.fm-button.fm-submit.keep-login-btn.keep-login-confirm-btn.primary",
                            timeout=30000,
                        )
                        await keep_button.click()
                        print("✅ 检测到“保持”按钮，已点击")
                    except Exception:
                        try:
                            await page.wait_for_selector(
                                "#alibaba-login-box", state="detached", timeout=30000
                            )
                            print("✅ 检测到iframe消失，登录完成")
                        except Exception:
                            print("⚠️ 登录可能未完成，请检查页面状态")
            else:
                print("未检测到短信验证提示，继续检查是否登录完成...")

                try:
                    keep_button = await frame.wait_for_selector(
                        "button.fm-button.fm-submit.keep-login-btn.keep-login-confirm-btn.primary",
                        timeout=30000,
                    )
                    await keep_button.click()
                    print("✅ 检测到“保持”按钮，已点击")
                except Exception:
                    try:
                        await page.wait_for_selector(
                            "#alibaba-login-box", state="detached", timeout=30000
                        )
                        print("✅ 检测到iframe消失，登录完成")
                    except Exception:
                        print("⚠️ 登录状态未确认，请手动检查页面")
        except Exception as e:
            print(f"登录流程出错：{e}")

        try:
            await context.storage_state(path=STATE_FILE)
            print(f"✅ 登录状态已保存到: {STATE_FILE}")
        except Exception as e:
            print(f"❌ 登录状态保存失败: {e}")

        # await browser.close()


if __name__ == "__main__":
    print("正在启动浏览器以进行登录...")
    asyncio.run(main())
