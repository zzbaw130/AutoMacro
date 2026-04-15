# 当AutoMacro被当作子模块时, onnxocr是子模块的子模块, 需要通过相对路径导入
try:
    from onnxocr.onnx_paddleocr import ONNXPaddleOcr, sav2Img
except:
    from .onnxocr.onnx_paddleocr import ONNXPaddleOcr, sav2Img

from pathlib import Path
import cv2
from types import SimpleNamespace
import pygetwindow as gw
import time
import dxcam
import win32gui, win32api
from pynput.keyboard import Controller as keyCtrl, Key
from pynput.mouse import Controller as mouseCtrl, Button
import random
import logging
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%a %d %b %Y %H:%M:%S",
)


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


def get_window_client_rect(hwnd: int) -> tuple[int, int, int, int]:
    """
    获取窗口客户区矩形坐标
    参数:
        hwnd: windows窗体句柄
    返回:
        形如 [左, 上, 右, 下] 的四个边界值
    """
    # 句柄为全屏
    if hwnd == 0:
        return 0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
    # 获取客户区矩形
    client_rect = win32gui.GetClientRect(hwnd)
    # 转换为屏幕坐标
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    right, bottom = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))

    return left, top, right, bottom


def isListEmpty(alist: list) -> bool:
    """
    判断List内部是否为空, 支持空字符串, 空列表嵌套等情况
    参数:
        alist: 待判断的List
    返回:
        为空则True, 否则False
    """
    if isinstance(alist, list):
        return all(map(isListEmpty, alist))
    return False


class Macro:
    def __init__(self, title: str = None, index: int = 0):
        """
        初始化Macro, 一个Macro用于操控一系列同名的进程, 利用index指定默认操作的进程
        参数:
            title: 进程标题名, 支持模糊搜索, 若不填写, 则默认选取整个屏幕
            index: 若存在多个同名的进程, 则可通过index指定具体使用哪个
        """
        if title:
            self.title: str = title
            # 将指定窗口放置最前
            self.windows: list[gw.Win32Window] = gw.getWindowsWithTitle(title)
            self.cur_index: int = index
            self.last_index: int = -1
            l, t, r, b = get_window_client_rect(self.windows[index]._hWnd)
            self.resolution: tuple[int, int] = (r - l, b - t)
        # 若未指定窗口, 则指定全屏
        else:
            self.title: str = "screen"
            # 创建一个简单的对象用以后续访问
            self.windows: list[gw.Win32Window] = [SimpleNamespace(**{"isActive": True, "_hWnd": 0})]
            self.cur_index: int = -1
            self.last_index: int = -1
            self.resolution: tuple[int, int] = (win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))

        self.keyboard = keyCtrl()
        self.mouse = mouseCtrl()
        self._cam = dxcam.create(output_color="BGR")
        self._ocr_handler = ONNXPaddleOcr(use_angle_cls=False, use_gpu=False)
        self._template_cache = {}

    def random_delay(self, sec: int, float_range: float = 0.1):
        """
        随机延迟
        参数:
            sec: 指定延迟的秒数
            float_range: 在指定秒数的基础上偏移指定范围, 默认偏移百分之十(0.1)
        """
        ms = sec * 1000
        random_delay_in_ms = random.randint(int(ms * (1 - float_range)), int(ms * (1 + float_range)))
        time.sleep(random_delay_in_ms / 1000)

    def switchToWindow(self, index: int = -1):
        """
        切换到指定的窗口, 可通过index指定切换到哪个窗口, 若不指定, 则激活初始化窗口
        参数:
            index: 窗口index
        """
        target_index = self.cur_index if index < 0 else index
        target_window = self.windows[target_index]
        logging.debug(f"目标窗口: {target_index}, 当前窗口: {self.cur_index}")
        # 窗口已经激活
        if target_window.isActive:
            logging.debug(f"窗口已激活, 无需切换")
            return
        # 第一次启动或激活自己可以使用activate
        if self.last_index == -1 or self.last_index == target_index:
            # 如果窗口最小化的话, 将其激活也无法放置最前, 因此需要先恢复
            if target_window.isMinimized:
                target_window.restore()
            target_window.activate()
            logging.debug(f"由主屏幕切换或激活自身, 使用active方法")
        # 从已经激活过的应用切换activate会报错, 使用缩小放大法
        else:
            target_window.minimize()
            target_window.restore()
            self.cur_index = target_index
            logging.debug(f"由另一窗口切换, 使用restore方法")

        self.last_index = target_index
        # 切换窗口有动画, 需要等待
        self.random_delay(0.5)

    def grab(
        self,
        roi: tuple[int, int, int, int] = None,
        save_path: Path | str = None,
    ) -> np.ndarray[np.uint8]:
        """
        截取指定roi区域的图片
        参数:
            roi: tuple[int, int, int, int], 形如[x, y, width, height]的roi区域
            save_path: Path | str, 截图保存路径, 若为None, 则不保存
        返回:
            截图图片的矩阵, 可用于后续OCR识别
        """
        # self.switchToWindow()
        rect = get_window_client_rect(self.windows[self.cur_index]._hWnd)

        # 指定ROI区域 x,y,w,h
        if roi is not None:
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
        参数:
            template_path: 模板图片路径,实际存储的模板图片命名格式为 resolution-x_y_w_h-name.png,
                其中resolution为当前应用分辨率, x,y,w,h为ROI, name为图片名称, 例如1920x1080-100_200_300_400-start_button.png
                正式使用时, 只需要传入name.png部分即可, 例如start_button.png, 程序会根据当前应用分辨率自动寻找对应的模板图片
            roi: 查找范围, 格式为(x, y, w, h), 若设置了此参数, 则会覆盖模板图片命名中的roi参数
            threshold: 匹配阈值, 默认0.8
        返回:
            返回值形如 (Ture, (10, 10), (0, 0, 1920, 1080)), 参数意义为(是否匹配成功, 在应用界面的中心坐标, 模板的roi)
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
                    roi = None
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

    def ocr(self, image_or_roi: Path | str | tuple[int, int, int, int] = None, saveResult: bool = False):
        """
        OCR识别文字
        参数:
            image_or_roi: 可以传入现有的图片路径, 也可以指定需要识别的ROI区域
        返回:
            识别到的文字
        """
        if image_or_roi is None or type(image_or_roi) is tuple:
            img = self.grab(roi=image_or_roi)
        else:
            img = cv2.imread(Path(image_or_roi))

        # 只ocr一行, 最终结果一定为单个
        res = self._ocr_handler.ocr(img)
        if saveResult:
            sav2Img(img, res)

        # 结果为空
        if isListEmpty(res):
            return ""
        # [[xxxx], ('检测文本', 0.9989050626754761)]
        box = res[0][0]
        ocr_text = box[1][0]
        return ocr_text

    def click(self, x, y, clicks: int = 1, interval: float = 0.1, button: str = "left", duration: float = 0.1):
        """
        鼠标点击
        参数:
            x: 点击的x坐标(相对于客户区)
            y: 点击的y坐标(相对于客户区)
            clicks: 点击次数
            interval: 点击间隔
            button: "left", "middle", "right" 分别代表鼠标左键、中键、右键
            duration: 按下鼠标后的持续时间, 然后松开, 视为一次点击
        """
        cl, ct, _, _ = get_window_client_rect(self.windows[self.cur_index]._hWnd)
        absolute_x = x + cl
        absolute_y = y + ct
        self.mouse.position = (absolute_x, absolute_y)
        time.sleep(0.02)
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
        """
        随机点击指定ROI区域中的一个位置
        参数:
            roi: 指定ROI区域
            clicks: 点击次数
            interval: 点击间隔
            button: "left", "middle", "right" 分别代表鼠标左键、中键、右键
            duration: 按下鼠标后的持续时间, 然后松开, 视为一次点击
        """
        l, t, w, h = roi

        random_x = random.randint(l, l + w)
        random_y = random.randint(t, t + h)
        self.click(random_x, random_y, clicks, interval, button, duration)

    def wheel_up(self, unit: int = 1):
        """
        鼠标滚轮向上滚动
        参数:
            unit: 滚动的格数
        """
        self.mouse.scroll(0, unit)

    def wheel_down(self, unit: int = 1):
        """
        鼠标滚轮向下滚动
        参数:
            unit: 滚动的格数
        """
        self.mouse.scroll(0, -unit)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float, button: str = "left"):
        """
        鼠标拖拽
        参数:
            x1: 起始点x坐标
            y1: 起始点y坐标
            x2: 终止点x坐标
            y2: 终止点y坐标
            duration: 模拟拖拽时间(按照60帧来进行模拟)
            button: "left", "middle", "right" 分别代表鼠标左键、中键、右键
        """
        cl, ct, _, _ = get_window_client_rect(self.windows[self.cur_index]._hWnd)
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
        """
        键盘按下
        参数:
            key: 单个按键, 请参照KB_MAPPING
        """
        self.keyboard.press(key if len(key) == 1 else KB_MAPPING[key])
        time.sleep(0.01)

    def key_up(self, key: str):
        """
        键盘抬起
        参数:
            key: 单个按键, 请参照KB_MAPPING
        """
        self.keyboard.release(key if len(key) == 1 else KB_MAPPING[key])
        time.sleep(0.01)

    def key_press(self, keys: str | list, duration: float = 0.1, interval: float = 0.1):
        """
        敲击键盘
        参数:
            keys: 需要键入的按键, 若为
            duration:
            interval:
        """

        # 用于处理字符串形式输入的key
        def press_key_str(key_str: str, duration: int, interval: int):
            # 若输入的字符串匹配上功能键, 则直接键入功能键
            if key_str in KB_MAPPING:
                self.keyboard.press(KB_MAPPING[key_str])
                time.sleep(duration)
                self.keyboard.release(KB_MAPPING[key_str])
            else:
                single_key_list = list(key_str)
                for i, sk in enumerate(single_key_list):
                    self.keyboard.press(sk)
                    time.sleep(duration)
                    self.keyboard.release(sk)
                    if i < len(single_key_list) - 1:
                        time.sleep(interval)

        # 用户输入的是一个字符串, 直接运行
        if type(keys) == str:
            press_key_str(keys, duration, interval)
        # 用户输入的是一个字符串列表, 分解为多个字符串依次运行
        else:
            keys_list = list(keys)
            for key_str in keys_list:
                press_key_str(key_str, duration, interval)
