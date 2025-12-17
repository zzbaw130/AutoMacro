from ctypes import windll
from pathlib import Path
from typing import TypedDict, Unpack

import cv2
import pygetwindow as gw
import time
import dxcam
import win32gui
import numpy as np
import pydirectinput as pdi


# windll.user32.SetProcessDPIAware()
class ActionParams(TypedDict, total=False):
    pre_delay: float
    post_delay: float


def get_window_client_rect(hwnd):
    # 获取客户区矩形
    client_rect = win32gui.GetClientRect(hwnd)
    # 转换为屏幕坐标
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

    return left, top, right, bottom


class Macro:
    def __init__(self, title: str):
        self.title: str = title
        # 将指定窗口放置最前
        self.window: gw.Win32Window = gw.getWindowsWithTitle(title)[0]
        self.switchToWindow()
        self.cam = dxcam.create(output_color="BGR")
        self.template_cache = {}

    def switchToWindow(self):
        if self.window.isActive:
            return
        # 如果窗口最小化的话, 将其激活也无法放置最前, 因此需要先恢复
        if self.window.isMinimized:
            self.window.restore()
        self.window.activate()
        # 切换窗口有动画, 需要等待
        time.sleep(0.5)

    def capture(
        self,
        roi: tuple[int, int, int, int] = (0, 0, 0, 0),
        save_path: Path | str = None,
    ):
        # self.switchToWindow()
        rect = get_window_client_rect(self.window._hWnd)
        # 指定ROI区域 x,y,w,h
        if roi != (0, 0, 0, 0):
            x, y, w, h = roi
            l, t, r, b = rect
            rect = (l + x, t + y, l + x + w, t + y + h)

        # 截图
        img = self.cam.grab(rect)

        # 存在偶尔无法捕获截图的情况
        if img is None:
            return self.capture(roi, save_path)

        # 需要保存为图片
        if save_path:
            # 创建路径目录
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(save_path), img)
        return img

    def find_image(
        self, template_path: Path | str, threshold=0.8
    ) -> tuple[bool, tuple[int, int], float]:
        """
        查找图像

        :param self: Description
        :param template_path: 模板图片路径
        :param threshold: 匹配阈值, 默认0.8
        :return: 返回值形如(是否匹配成功, 在应用界面的坐标, 匹配度)
        """
        # 查询缓存
        if str(template_path) not in self.template_cache:
            template = cv2.imread(template_path)
            # 根据文件名称计算roi
            template_name = Path(template_path).stem
            try:
                roi = tuple([int(i) for i in template_name.split("_")[-4:]])
            except ValueError:
                roi = (0, 0, 0, 0)
            # 根据路径缓存图片
            self.template_cache.update({str(template_path): (template, roi)})
        else:
            template, roi = self.template_cache[str(template_path)]

        # 获取切片
        screenshot = self.capture(roi=roi)

        # 存在偶尔无法捕获截图的情况
        if screenshot is None:
            return False, None, 0.0

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            center_x = max_loc[0] + self.window.left + roi[0] + template.shape[1] // 2
            center_y = max_loc[1] + self.window.top + roi[1] + template.shape[0] // 2
            return True, (center_x, center_y), max_val
        return False, None, max_val

    def click(self, x, y, clicks, interval, button="left", duration=None):
        pdi.click(x, y, clicks, interval, button, duration)

    def drag(self, x1, y1, x2, y2):
        pdi.mouseDown(x1, y1)
        pdi.mouseUp(x2, y2)

    def keyDown(self, key):
        pdi.keyDown(key)

    def keyUp(self, key):
        pdi.keyUp(key)

    def keyPress(self, keys: str, druation=0.01, interval=0.01):
        keys = list(keys)
        for key in keys:
            pdi.keyDown(key)
            time.sleep(druation)
            pdi.keyUp(key)
            time.sleep(interval)


pm = Macro("此电脑")

res = pm.find_image("ces_717_191_45_28.png")
x, y = res[1]
pm.click(x, y, clicks=2, interval=0.1)
