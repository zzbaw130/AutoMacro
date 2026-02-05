import pygetwindow as gw
import cv2
import time

hwnd = gw.getWindowsWithTitle("燕云十六声")[0]._hWnd

from ScreenShot import BitBlt, PrintWindow, WindowsGraphicsCapture

# wgc = WindowsGraphicsCapture(hwnd)

while True:
    s = time.time()
    PrintWindow(hwnd, 0, 0, 1600, 900)
    e = time.time()
    print(f"FPS: {1/(e - s)}")


# 显示到屏幕
# cv2.namedWindow("img")  # 命名窗口
# cv2.imshow("img", pic)  # 显示
# cv2.waitKey(0)
# cv2.destroyAllWindows()
