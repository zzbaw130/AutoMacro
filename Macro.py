from ctypes import windll
from pathlib import Path
from typing import TypedDict, Unpack

import cv2
import pygetwindow as gw
import time
import dxcam
import win32gui
from pynput.keyboard import Controller as keyCtrl, Key
from pynput.mouse import Controller as mouseCtrl, Button
import random
from .onnxocr.onnx_paddleocr import ONNXPaddleOcr, sav2Img


# windll.user32.SetProcessDPIAware()
class ActionParams(TypedDict, total=False):
    pre_delay: float
    post_delay: float


BTN_MAPPING = {
    "left": Button.left,
    "right": Button.right,
    "middle": Button.middle,
}

KB_MAPPING = {
    "alt": Key.alt,
    "l_alt": Key.alt_l,
    "r_alt": Key.alt_r,
    "gr_alt": Key.alt_gr,
    "backspace": Key.backspace,
    "caps_lock": Key.caps_lock,
    "cmd": Key.cmd,
    "l_cmd": Key.cmd_l,
    "r_cmd": Key.cmd_r,
    "ctrl": Key.ctrl,
    "l_ctrl": Key.ctrl_l,
    "r_ctrl": Key.ctrl_r,
    "delete": Key.delete,
    "end": Key.end,
    "enter": Key.enter,
    "esc": Key.esc,
    "f1": Key.f1,
    "f2": Key.f2,
    "f3": Key.f3,
    "f4": Key.f4,
    "f5": Key.f5,
    "f6": Key.f6,
    "f7": Key.f7,
    "f8": Key.f8,
    "f9": Key.f9,
    "f10": Key.f10,
    "f11": Key.f11,
    "f12": Key.f12,
    "f13": Key.f13,
    "f14": Key.f14,
    "f15": Key.f15,
    "f16": Key.f16,
    "f17": Key.f17,
    "f18": Key.f18,
    "f19": Key.f19,
    "f20": Key.f20,
    "home": Key.home,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "page_down": Key.page_down,
    "page_up": Key.page_up,
    "shift": Key.shift,
    "l_shift": Key.shift_l,
    "r_shift": Key.shift_r,
    "space": Key.space,
    "tab": Key.tab,
    "media_play_pause": Key.media_play_pause,
    "media_volume_mute": Key.media_volume_mute,
    "media_volume_down": Key.media_volume_down,
    "media_volume_up": Key.media_volume_up,
    "media_previous": Key.media_previous,
    "media_next": Key.media_next,
    "insert": Key.insert,
    "menu": Key.menu,
    "num_lock": Key.num_lock,
    "pause": Key.pause,
    "print_screen": Key.print_screen,
    "scroll_lock": Key.scroll_lock,
}


def get_window_client_rect(hwnd) -> tuple[int, int, int, int]:
    # 获取客户区矩形
    client_rect = win32gui.GetClientRect(hwnd)
    # 转换为屏幕坐标
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

    return left, top, right, bottom


def isListEmpty(alist: list) -> bool:
    if isinstance(alist, list):
        return all(map(isListEmpty, alist))
    return False


class Macro:
    def __init__(self, title: str):
        self.title: str = title
        # 将指定窗口放置最前
        self.window: gw.Win32Window = gw.getWindowsWithTitle(title)[0]
        l, t, r, b = get_window_client_rect(self.window._hWnd)
        self.resolution = (r - l, b - t)
        self.switchToWindow()
        self.keyboard = keyCtrl()
        self.mouse = mouseCtrl()
        self._cam = dxcam.create(output_color="BGR")
        self._ocr_handler = ONNXPaddleOcr(use_angle_cls=False, use_gpu=False)
        self._template_cache = {}

    def switchToWindow(self):
        if self.window.isActive:
            return
        # 如果窗口最小化的话, 将其激活也无法放置最前, 因此需要先恢复
        if self.window.isMinimized:
            self.window.restore()
        self.window.activate()
        # 切换窗口有动画, 需要等待
        time.sleep(0.5)

    def grab(
        self,
        roi: tuple[int, int, int, int] = (0, 0, 0, 0),
        save_path: Path | str = None,
    ):
        # self.switchToWindow()
        rect = get_window_client_rect(self.window._hWnd)

        # 指定ROI区域 x,y,w,h
        if roi != (0, 0, 0, 0):
            x, y, w, h = roi
            cl, ct, _, _ = rect
            rect = (cl + x, ct + y, cl + x + w, ct + y + h)

        # 截图
        img = self._cam.grab(rect)

        # 存在偶尔无法捕获截图的情况
        if img is None:
            return self.grab(roi, save_path)

        # 需要保存为图片
        if save_path:
            # 创建路径目录
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(save_path), img)
        return img

    def find_image(
        self, template_path: Path | str, roi: tuple[int, int, int, int] = None, threshold=0.8
    ) -> tuple[bool, tuple[int, int], float]:
        """
        查找图像

        :param self: Description
        :param template_path: 模板图片路径,
            实际存储的模板图片命名格式为resolution-x_y_w_h-name.png, 其中resolution为当前应用分辨率,
            x,y,w,h为ROI, name为图片名称, 例如1920x1080-100_200_300_400-start_button.png
            正式使用时, 只需要传入name.png部分即可, 例如start_button.png, 程序会根据当前应用分辨率自动寻找对应的模板图片
        :param roi: 查找范围, 格式为(x, y, w, h), 若设置了此参数, 则会覆盖模板图片命名中的roi参数
        :param threshold: 匹配阈值, 默认0.8
        :return: 返回值形如(是否匹配成功, 在应用界面的中心坐标, 模板的roi)
        """
        # 寻找模板图片
        tp = Path(template_path)
        w, h = self.resolution
        template_path = list(tp.parent.glob(f"{w}x{h}-{tp.stem}-*{tp.suffix}"))[0]
        # 查询缓存
        if str(template_path) not in self._template_cache:
            template = cv2.imread(template_path)
            # 如果没有设置roi, 则尝试从文件名中解析roi
            if roi is None:
                # 根据文件名称计算roi
                template_name = Path(template_path).stem
                try:
                    roi = tuple([int(i) for i in template_name.split("-")[-1].split("_")])
                except ValueError:
                    roi = (0, 0, 0, 0)
            # 根据路径缓存图片
            self._template_cache.update({str(template_path): (template, roi)})
        else:
            template, roi = self._template_cache[str(template_path)]

        # 获取切片
        screenshot = self.grab(roi=roi)

        # 存在偶尔无法捕获截图的情况
        if screenshot is None:
            return False, None, None

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= threshold:
            center_x = max_loc[0] + roi[0] + template.shape[1] // 2
            center_y = max_loc[1] + roi[1] + template.shape[0] // 2
            template_roi = (roi[0] + max_loc[0], roi[1] + max_loc[1], template.shape[1], template.shape[0])
            return True, (center_x, center_y), template_roi
        return False, None, None

    def ocr(self, image_or_roi: Path | str | tuple[int, int, int, int]):
        if type(image_or_roi) is tuple:
            img = self.grab(roi=image_or_roi)
        else:
            img = cv2.imread(Path(image_or_roi))

        # 只ocr一行, 最终结果一定为单个
        res = self._ocr_handler.ocr(img)
        # 结果为空
        if isListEmpty(res):
            return ""
        # [[xxxx], ('检测文本', 0.9989050626754761)]
        box = res[0][0]
        ocr_text = box[1][0]
        return ocr_text

    def click(self, x, y, clicks: int = 1, interval: float = 0.01, button: str = "left", duration: float = 0.01):
        cl, ct, _, _ = get_window_client_rect(self.window._hWnd)
        absolute_x = x + cl
        absolute_y = y + ct
        self.mouse.position = (absolute_x, absolute_y)
        time.sleep(0.01)
        for i in range(clicks):
            self.mouse.press(BTN_MAPPING[button])
            time.sleep(duration)
            self.mouse.release(BTN_MAPPING[button])
            if i < clicks - 1:
                time.sleep(interval)

    def random_click(
        self,
        roi: tuple[int, int, int, int],
        clicks: int = 1,
        interval: float = 0.0,
        button: str = "left",
        duration: float = 0.0,
    ):
        l, t, w, h = roi

        random_x = random.randint(l, l + w)
        random_y = random.randint(t, t + h)
        self.click(random_x, random_y, clicks, interval, button, duration)

    def wheel_up(self, unit: int = 1):
        self.mouse.scroll(0, unit)

    def wheel_down(self, unit: int = 1):
        self.mouse.scroll(0, -unit)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float, button: str = "left"):
        cl, ct, _, _ = get_window_client_rect(self.window._hWnd)
        absolute_x1 = x1 + cl
        absolute_y1 = y1 + ct

        absolute_x2 = x2 + cl
        absolute_y2 = y2 + ct
        # 放置于起始点
        self.mouse.position = (absolute_x1, absolute_y1)
        fps = 60
        # 计算每帧移动的距离
        x_move = (absolute_x2 - absolute_x1) / fps
        y_move = (absolute_y2 - absolute_y1) / fps
        # 执行拖拽
        self.mouse.press(BTN_MAPPING[button])
        for i in range(60):
            self.mouse.move(x_move, y_move)
            time.sleep(duration / fps)
        self.mouse.release(BTN_MAPPING[button])

    def key_down(self, key: str):
        self.keyboard.press(key if len(key) == 1 else KB_MAPPING[key])
        time.sleep(0.01)

    def key_up(self, key: str):
        self.keyboard.release(key if len(key) == 1 else KB_MAPPING[key])
        time.sleep(0.01)

    def key_press(self, keys: str | list, duration: float = 0.01, interval: float = 0.01):
        keys = list(keys)
        for i, key in enumerate(keys):
            m_key = key if len(key) == 1 else KB_MAPPING[key]
            self.keyboard.press(m_key)
            time.sleep(duration)
            self.keyboard.release(m_key)
            if i < len(keys) - 1:
                time.sleep(interval)
