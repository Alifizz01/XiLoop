"""Regenerate the README screenshots from the live Studio UI.

    pip install playwright pillow
    python assets/make_screenshots.py          # uses your installed Chrome, no browser download

Starts its own API server on a spare port, drives the real UI, writes the PNG/GIF files next to this script.
"""
import io
import os
import threading

from PIL import Image
from playwright.sync_api import sync_playwright

from xiloop.server import make_server

OUT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)


def set_input(page, sel, value):
    page.eval_on_selector(sel, "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); }", value)


def main():
    srv = make_server(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", args=["--lang=en-US"])
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5, locale="en-US")
        page.goto(url)
        page.wait_for_selector(".meter output")
        page.wait_for_timeout(600)
        shot = lambda name, **kw: page.screenshot(path=os.path.join(OUT, name), **kw)

        # 1. Tune - default actuator + PID
        shot("tune.png")

        # 2. Animated tuning: sweep kd and watch overshoot fall
        frames = []
        for kd in [0.0, 0.02, 0.04, 0.06, 0.08, 0.1, 0.13, 0.16, 0.2, 0.25, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05]:
            set_input(page, '#gains input[type=range][data-g="kd"]', str(kd))
            page.wait_for_timeout(180)
            png = page.screenshot(clip={"x": 0, "y": 52, "width": 1440, "height": 848})
            frames.append(Image.open(io.BytesIO(png)).convert("RGB").resize((960, 565), Image.LANCZOS))
        frames[0].save(os.path.join(OUT, "tuning.gif"), save_all=True, append_images=frames[1:],
                       duration=260, loop=0, optimize=True)
        set_input(page, '#gains input[type=range][data-g="kd"]', "0.05")

        # 3. Transfer-function plant typed in the GUI
        page.select_option("#plant-type", "transfer_function")
        page.dispatch_event("#plant-type", "change")
        set_input(page, '#plant-params input[data-p="num"]', "4")
        set_input(page, '#plant-params input[data-p="den"]', "1 0.6 4")
        set_input(page, '#gains input[type=range][data-g="kp"]', "3")
        set_input(page, '#gains input[type=range][data-g="ki"]', "3")
        set_input(page, '#gains input[type=range][data-g="kd"]', "0.8")
        page.wait_for_timeout(500)
        shot("transfer_function.png")

        # 4. Firmware over TCP, real time, captured mid-run (pen head visible)
        page.select_option("#plant-type", "actuator")
        page.dispatch_event("#plant-type", "change")
        for g, v in {"kp": "2", "ki": "1", "kd": "0.05"}.items():
            set_input(page, f'#gains input[type=range][data-g="{g}"]', v)
        page.click('#dev-type button[data-v="socket"]')
        set_input(page, "#sock-port", "5571")
        page.click("#board-toggle")
        page.wait_for_selector(".board.on")
        page.check("#sc-rt")
        page.click("#run")
        page.wait_for_timeout(1300)
        shot("firmware_live.png")
        page.wait_for_timeout(2500)

        # 5. API dialog
        page.uncheck("#sc-rt")
        page.click("#api-open")
        page.click('#api-lang button[data-v="python"]')
        page.wait_for_timeout(200)
        shot("api_call.png")
        page.keyboard.press("Escape")

        # 6. Verify - passing and failing campaigns
        page.click('#dev-type button[data-v="pid"]')
        page.click('.mode[data-mode="verify"]')
        page.select_option("#ex-pick", label="Actuator PID verification")
        page.click("#v-run")
        page.wait_for_selector(".stamp.pass")
        page.wait_for_timeout(500)
        shot("verify_pass.png")

        set_input(page, '#gains input[type=range][data-g="kp"]', "12")
        set_input(page, '#gains input[type=range][data-g="kd"]', "0")
        page.click("#v-run")
        page.wait_for_selector(".stamp.fail")
        page.wait_for_timeout(500)
        shot("verify_fail.png")
        browser.close()
    srv.shutdown()
    print("screenshots written to", OUT)


if __name__ == "__main__":
    main()
