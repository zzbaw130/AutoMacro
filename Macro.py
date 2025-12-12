from ctypes import windll
from pathlib import Path
from typing import TypedDict, Unpack

import cv2
import pygetwindow as gw
import time
import dxcam
import win32gui


# windll.user32.SetProcessDPIAware()
class CaptureParams(TypedDict, total=False):
    roi: tuple[int, int, int, int]
    savePath: Path | str


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

    def capture(self, **kwargs: Unpack[CaptureParams]):
        # self.switchToWindow()
        rect = get_window_client_rect(self.window._hWnd)
        # 指定ROI区域 x,y,w,h
        if "roi" in kwargs and kwargs["roi"] != (0, 0, 0, 0):
            x, y, w, h = kwargs["roi"]
            l, t, r, b = rect
            rect = (l + x, t + y, l + x + w, t + y + h)

        # 截图
        img = self.cam.grab(rect)

        if img is None:
            return None

        # 需要保存为图片
        if "savePath" in kwargs and kwargs["savePath"] is not None:
            path = Path(kwargs["savePath"])
            cv2.imwrite(str(path), img)
        return img

    def find_image(self, template_path: Path | str, threshold=0.8):
        """查找图像"""
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

    def action(self):
        pass

    def control_decorator(self, pre_delay, post_delay):
        time.sleep(pre_delay / 1000)
        self.action()
        time.sleep(post_delay / 1000)


pm = Macro("此电脑")

while True:
    s = time.time()
    res = pm.find_image("ces_717_191_45_28.png")
    e = time.time()
    print(f"耗时{e - s}")
    print(res)
    print()
    time.sleep(0.2)
