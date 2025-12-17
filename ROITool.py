"""
图像ROI选择工具 (Image ROI Selector Tool)

功能概述：
该应用程序是一个基于PyQt5的图像处理工具，允许用户：
1. 打开常见格式的图像文件(PNG/JPG/JPEG/BMP)
2. 自动缩放超大图像(大于1500px)保持宽高比
3. 通过鼠标拖动在图像上选择矩形感兴趣区域(ROI)
4. 实时显示ROI坐标和尺寸（包括原始图像尺寸）
5. 重置已选择的ROI区域
6. 导出所选ROI区域为独立图像文件

主要组件：
1. ROISelector：自定义图形视图组件
   - 图像加载与自动缩放
   - ROI选择交互逻辑
   - 坐标转换（缩放图↔原始图）

2. MainWindow：主窗口界面
   - 文件打开/保存功能
   - 按钮控制（打开/重置/导出）
   - 状态信息显示

技术栈：
- Python 3.x
- PyQt5 (GUI框架)
- OpenCV (图像处理)
- NumPy (数据转换)

使用说明：
1. 点击"打开图像"按钮选择图像文件
2. 在图像上按住鼠标左键拖动选择ROI区域
3. 实时显示ROI的位置和尺寸信息
4. 使用"重置ROI"按钮可重新选择
5. 点击"导出ROI"保存选择区域到文件

作者：ziyuhaokun
日期：2025-07-31
版本：0.1-beta
"""

import pathlib
import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QGraphicsView,
    QGraphicsScene,
    QLabel,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QImage, QPixmap, QPen, QBrush, QColor


class ROISelector(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.image_item = None
        self.origin_image = None  # 原始图像数据
        self.scale_ratio = 1.0
        self.roi_item = None
        self.dragging = False
        self.start_point = None
        self.roi_rect = None
        
        # 缩放相关
        self.zoom_factor = 1.0  # 当前缩放倍率
        self.min_zoom = 0.1  # 最小缩放
        self.max_zoom = 10.0  # 最大缩放
        
        # 右键拖动相关
        self.panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0

        # 状态标签
        self.status_label = QLabel("拖动鼠标选择ROI")
        self.status_label.setAlignment(Qt.AlignCenter)

    def load_image(self, image_path):
        # 读取图像
        orig_image = cv2.imread(image_path)
        if orig_image is None:
            return False

        # 获取原始尺寸
        h, w = orig_image.shape[:2]

        # 判断是否需要缩放
        # if w > 1500 or h > 1500:
        #     # 计算缩放比例 (保持宽高比)
        #     scale = 1500 / max(w, h)
        #     new_w = int(w * scale)
        #     new_h = int(h * scale)
        #     resized_image = cv2.resize(orig_image, (new_w, new_h))
        #     self.scale_ratio = scale
        #     print(f"图像已缩放: {w}x{h} -> {new_w}x{new_h}")
        # else:
        resized_image = orig_image
        self.scale_ratio = 1.0

        # 存储原始图像和显示图像
        self.origin_image = orig_image  # NumPy数组
        self.resized_image = resized_image
        self.image_path = image_path

        # 转换为QImage (OpenCV使用BGR, Qt使用RGB)
        rgb_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # 创建QPixmap并添加到场景
        pixmap = QPixmap.fromImage(q_img)
        self.scene.clear()
        self.image_item = self.scene.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))

        # 重置视图缩放
        self.resetTransform()
        return True

    def get_original_roi(self):
        """获取原始图像中的ROI坐标"""
        if self.roi_rect is None:
            return (0, 0, 0, 0)  # 返回默认值而不是None

        # 将缩放后的坐标转换回原始图像坐标
        x = int(self.roi_rect.x() / self.scale_ratio)
        y = int(self.roi_rect.y() / self.scale_ratio)
        w = int(self.roi_rect.width() / self.scale_ratio)
        h = int(self.roi_rect.height() / self.scale_ratio)

        return x, y, w, h

    def mousePressEvent(self, event):
        if self.image_item and event.button() == Qt.LeftButton:
            self.dragging = True
            self.start_point = self.mapToScene(event.pos())
            size = self.resized_image.shape
            self.start_point.setX(max(0, min(self.start_point.x(), size[1])))
            self.start_point.setY(max(0, min(self.start_point.y(), size[0])))

            # 移除现有的ROI图形
            if self.roi_item:
                self.scene.removeItem(self.roi_item)
                self.roi_item = None

            # 创建新的ROI矩形
            self.roi_rect = QRectF(self.start_point, self.start_point)
            self.roi_item = self.scene.addRect(
                self.roi_rect, QPen(Qt.red, 2), QBrush(QColor(255, 0, 0, 50))
            )
        elif self.image_item and event.button() == Qt.RightButton:
            # 右键开始拖动视图
            self.panning = True
            self.pan_start_x = event.x()
            self.pan_start_y = event.y()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.panning:
            # 右键拖动视图
            delta_x = event.x() - self.pan_start_x
            delta_y = event.y() - self.pan_start_y
            
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta_x
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta_y
            )
            
            self.pan_start_x = event.x()
            self.pan_start_y = event.y()
        elif self.image_item and self.dragging:
            # 左键拖动选择ROI
            end_point = self.mapToScene(event.pos())
            size = self.resized_image.shape
            end_point.setX(max(0, min(end_point.x(), size[1])))
            end_point.setY(max(0, min(end_point.y(), size[0])))

            # 更新矩形
            self.roi_rect = QRectF(self.start_point, end_point).normalized()
            if self.roi_item:
                self.roi_item.setRect(self.roi_rect)

            # 更新状态
            if self.roi_rect:  # 确保roi_rect存在
                x, y, w, h = self.get_original_roi()
                zoom_percent = int(self.zoom_factor * 100)
                self.status_label.setText(f"ROI: [X: {x}, Y: {y}, W: {w}, H: {h}] | 缩放: {zoom_percent}%")
        else:
            # 普通鼠标移动时实时显示坐标
            if self.image_item:
                pos = self.mapToScene(event.pos())
                size = self.resized_image.shape
                
                # 确保坐标在图像范围内
                if 0 <= pos.x() <= size[1] and 0 <= pos.y() <= size[0]:
                    # 转换为原始图像坐标
                    orig_x = int(pos.x() / self.scale_ratio)
                    orig_y = int(pos.y() / self.scale_ratio)
                    zoom_percent = int(self.zoom_factor * 100)
                    self.status_label.setText(f"坐标: [X: {orig_x}, Y: {orig_y}] | 缩放: {zoom_percent}%")

    def mouseReleaseEvent(self, event):
        if self.dragging and event.button() == Qt.LeftButton:
            self.dragging = False
            # 最终ROI显示
            if self.roi_rect:
                x, y, w, h = self.get_original_roi()
                zoom_percent = int(self.zoom_factor * 100)
                self.status_label.setText(f"选择完成: [X: {x}, Y: {y}, W: {w}, H: {h}] | 缩放: {zoom_percent}%")
                print(f"选择的ROI (原始尺寸): X={x}, Y={y}, Width={w}, Height={h}")
        elif self.panning and event.button() == Qt.RightButton:
            # 右键释放，停止拖动
            self.panning = False
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        """处理鼠标滚轮事件，实现Ctrl+滚轮缩放"""
        # 检查是否按下Ctrl键
        if event.modifiers() == Qt.ControlModifier and self.image_item:
            # 获取滚轮滚动方向
            delta = event.angleDelta().y()
            
            # 计算缩放因子 (每次滚动10%)
            if delta > 0:
                scale_factor = 1.1
            else:
                scale_factor = 0.9
            
            # 计算新的缩放倍率
            new_zoom = self.zoom_factor * scale_factor
            
            # 限制缩放范围
            if new_zoom < self.min_zoom or new_zoom > self.max_zoom:
                return
            
            # 获取鼠标在场景中的位置（缩放前）
            old_pos = self.mapToScene(event.pos())
            
            # 应用缩放
            self.scale(scale_factor, scale_factor)
            self.zoom_factor = new_zoom
            
            # 获取鼠标在场景中的位置（缩放后）
            new_pos = self.mapToScene(event.pos())
            
            # 调整视图位置，使鼠标指向的点保持不变
            delta_pos = new_pos - old_pos
            self.translate(delta_pos.x(), delta_pos.y())
            
            # 更新状态显示
            zoom_percent = int(self.zoom_factor * 100)
            if self.roi_rect:
                x, y, w, h = self.get_original_roi()
                self.status_label.setText(f"ROI: [X: {x}, Y: {y}, W: {w}, H: {h}] | 缩放: {zoom_percent}%")
            else:
                self.status_label.setText(f"拖动鼠标选择ROI | 缩放: {zoom_percent}%")
        else:
            # 如果没有按Ctrl，使用默认滚动行为
            super().wheelEvent(event)

    def reset_roi(self):
        """重置当前ROI选择"""
        if self.roi_item:
            self.scene.removeItem(self.roi_item)
            self.roi_item = None
        self.roi_rect = None
        self.status_label.setText("ROI已重置")
        print("ROI已重置")

    def export_roi(self):
        """导出当前选择的ROI为图像文件"""
        # 检查是否加载了图像 (使用is None检查而不是布尔值判断)
        if self.origin_image is None:
            return False, "没有加载图像", None

        # 检查是否选择了ROI
        if self.roi_rect is None:
            return False, "没有选择ROI区域", None

        # 获取原始图像中的ROI坐标
        x, y, w, h = self.get_original_roi()

        # 确保ROI区域在图像范围内
        img_height, img_width = self.origin_image.shape[:2]
        if x >= img_width or y >= img_height or w <= 0 or h <= 0:
            return False, "无效的ROI区域", None

        # 调整坐标边界
        x = max(0, min(x, img_width - 1))
        y = max(0, min(y, img_height - 1))
        w = min(w, img_width - x)
        h = min(h, img_height - y)

        # 提取ROI区域
        roi = self.origin_image[y : y + h, x : x + w]

        return True, roi, (x, y, w, h)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图像ROI选择器")
        self.setGeometry(100, 100, 1200, 800)

        # 创建主控件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 创建ROI选择器
        self.roi_selector = ROISelector()
        layout.addWidget(self.roi_selector)

        # 添加按钮布局
        btn_layout = QHBoxLayout()

        # 打开文件按钮
        self.btn_open = QPushButton("打开图像")
        self.btn_open.clicked.connect(self.open_image)
        btn_layout.addWidget(self.btn_open)

        # 重置按钮
        self.btn_reset = QPushButton("重置ROI")
        self.btn_reset.clicked.connect(self.roi_selector.reset_roi)
        btn_layout.addWidget(self.btn_reset)

        # 导出ROI按钮
        self.btn_export = QPushButton("导出ROI")
        self.btn_export.clicked.connect(self.export_roi)
        btn_layout.addWidget(self.btn_export)

        layout.addLayout(btn_layout)

        # 添加状态标签
        layout.addWidget(self.roi_selector.status_label)

    def open_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开图像", "", "图像文件 (*.png *.jpg *.jpeg *.bmp)"
        )

        if file_path:
            success = self.roi_selector.load_image(file_path)
            if success:
                self.roi_selector.status_label.setText("拖动鼠标选择ROI")
                # 重置ROI状态
                self.roi_selector.reset_roi()
            else:
                self.roi_selector.status_label.setText("无法加载图像")
                # 确保清除无效图像
                self.roi_selector.origin_image = None
                self.roi_selector.image_path = None

    def export_roi(self):
        """处理导出ROI图像的操作"""
        success, roi_img, roi_coords = self.roi_selector.export_roi()

        if not success:
            if roi_img == "没有加载图像":
                QMessageBox.warning(self, "导出失败", "请先打开一个图像文件")
            elif roi_img == "没有选择ROI区域":
                QMessageBox.warning(self, "导出失败", "请先选择一个ROI区域")
            else:
                QMessageBox.warning(self, "导出失败", "无法导出ROI区域：" + roi_img)
            return

        # 获取保存路径
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存ROI图像",
            "",
            "PNG图像 (*.png);;JPEG图像 (*.jpg *.jpeg);;所有文件 (*)",
        )

        if not save_path:
            return  # 用户取消了保存操作

        # 添加文件后缀标识
        name, suffix = save_path.split(".")
        x, y, w, h = roi_coords
        save_path = f"{name}_{x}_{y}_{w}_{h}.{suffix}"

        # 保存ROI图像
        try:
            cv2.imwrite(save_path, roi_img)
            # 检查是否保存成功
            saved_image = cv2.imread(save_path)
            if saved_image is None:
                raise RuntimeError("保存文件失败，可能是文件路径无效或格式不受支持")

            # 更新状态
            self.roi_selector.status_label.setText(
                f"ROI已导出: [X:{x}, Y:{y}, W:{w}, H{h}] 保存至: {save_path}"
            )
            QMessageBox.information(
                self,
                "导出成功",
                f"ROI图像已成功保存到:\n{save_path}\n尺寸: {w} x {h} 像素",
            )
            print(f"ROI图像已导出: {save_path} (尺寸: {w}x{h})")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存图像时出错:\n{str(e)}")
            self.roi_selector.status_label.setText("ROI导出失败: " + str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
