import asyncio

from winsdk.windows.ai.machinelearning import LearningModelDevice, LearningModelDeviceKind
from winsdk.windows.media.capture import MediaCapture
from winsdk.windows.graphics.capture.interop import create_for_window
from winsdk.windows.graphics.capture import (
    Direct3D11CaptureFramePool,
    Direct3D11CaptureFrame,
)
from winsdk.windows.graphics.directx import DirectXPixelFormat
from winsdk.system import Object
from winsdk.windows.graphics.imaging import (
    SoftwareBitmap,
    BitmapBufferAccessMode,
    BitmapBuffer,
)

import numpy as np
import win32gui, win32ui, win32con
from ctypes import windll


# source code from https://github.com/Avasam/AutoSplit/blob/master/src/utils.py
# and from https://github.com/pywinrt/python-winsdk/issues/11
def get_direct3d_device():
    try:
        direct_3d_device = LearningModelDevice(LearningModelDeviceKind.DIRECT_X_HIGH_PERFORMANCE).direct3_d11_device
    except:  # TODO: Unknown potential error, I don't have an older Win10 machine to test.
        direct_3d_device = None
    if not direct_3d_device:
        # Note: Must create in the same thread (can't use a global) otherwise when ran from not the main thread it will raise:
        # OSError: The application called an interface that was marshalled for a different thread
        media_capture = MediaCapture()

        async def coroutine():
            await (media_capture.initialize_async() or asyncio.sleep(0))

        asyncio.run(coroutine())
        direct_3d_device = (
            media_capture.media_capture_settings and media_capture.media_capture_settings.direct3_d11_device
        )
    if not direct_3d_device:
        raise OSError("Unable to initialize a Direct3D Device.")
    return direct_3d_device


class WindowsGraphicsCapture:
    def __init__(self, hwnd) -> None:
        self.device = get_direct3d_device()
        self.item = create_for_window(hwnd)
        self.frame_pool = None
        self.session = None

    async def _get_frame(self):
        event_loop = asyncio.get_running_loop()
        # create frame pool
        self.frame_pool = Direct3D11CaptureFramePool.create_free_threaded(
            self.device,
            DirectXPixelFormat.B8_G8_R8_A8_UINT_NORMALIZED,
            1,
            self.item.size,
        )
        # create capture session
        self.session = self.frame_pool.create_capture_session(self.item)
        self.session.is_border_required = False
        self.session.is_cursor_capture_enabled = False
        fut = event_loop.create_future()

        # callback
        def frame_arrived_callback(frame_pool: Direct3D11CaptureFramePool, event_args: Object):
            frame: Direct3D11CaptureFrame = frame_pool.try_get_next_frame()
            fut.set_result(frame)
            self.session.close()

        # set callback
        self.frame_pool.add_frame_arrived(lambda fp, o: event_loop.call_soon_threadsafe(frame_arrived_callback, fp, o))

        # start capture
        self.session.start_capture()

        # await frame and transform frame to bitmap
        frame_fut: Direct3D11CaptureFrame = await fut
        software_bitmap: SoftwareBitmap = await SoftwareBitmap.create_copy_from_surface_async(frame_fut.surface)

        # bitmap -> ndarray
        buffer: BitmapBuffer = software_bitmap.lock_buffer(BitmapBufferAccessMode.READ_WRITE)
        image = np.frombuffer(buffer.create_reference(), dtype=np.uint8)
        image.shape = (self.item.size.height, self.item.size.width, 4)
        return image

    def grab(self):
        return asyncio.run(self._get_frame())


def BitBlt(hwnd):
    # 获取句柄窗口的大小信息
    left, top, right, bot = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bot - top
    # 返回句柄窗口的设备环境，覆盖整个窗口，包括非客户区，标题栏，菜单，边框
    hWndDC = win32gui.GetWindowDC(hwnd)
    # 创建设备描述表
    mfcDC = win32ui.CreateDCFromHandle(hWndDC)
    # 创建内存设备描述表
    saveDC = mfcDC.CreateCompatibleDC()
    # 创建位图对象准备保存图片
    saveBitMap = win32ui.CreateBitmap()
    # 为bitmap开辟存储空间
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    # 将截图保存到saveBitMap中
    saveDC.SelectObject(saveBitMap)
    # 保存bitmap到内存设备描述表
    saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)
    ###获取位图信息
    signedIntsArray = saveBitMap.GetBitmapBits(True)
    # 内存释放
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hWndDC)
    # 保存到文件
    img = np.frombuffer(signedIntsArray, dtype="uint8")
    img = img.reshape(height, width, 4)
    return img


windll.user32.SetProcessDPIAware()


def PrintWindow(hwnd, x1, y1, x2, y2):
    w = x2 - x1
    h = y2 - y1
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bitmap)
    windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
    bmpinfo = bitmap.GetInfo()
    bmpstr = bitmap.GetBitmapBits(True)
    img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4))
    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    return img
