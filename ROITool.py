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
    QGraphicsTextItem,
    QInputDialog,
)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QImage, QPixmap, QPen, QBrush, QColor, QPainter


class ROISelector(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.image_item = None
        self.origin_image = None  # 原始图像数据
        self.scale_ratio = 1.0
        self.roi_items = []
        self.active_roi_item = None
        self.dragging = False
        self.start_point = None
        self.active_roi_rect = None

        # 缩放相关
        self.zoom_factor = 1.0  # 当前缩放倍率
        self.min_zoom = 0.1  # 最小缩放
        self.max_zoom = 20.0  # 最大缩放

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

    def get_original_roi_from_rect(self, rect):
        """获取原始图像中的ROI坐标"""
        if rect is None:
            return (0, 0, 0, 0)

        # 将缩放后的坐标转换回原始图像坐标
        x = int(rect.x() / self.scale_ratio)
        y = int(rect.y() / self.scale_ratio)
        w = int(rect.width() / self.scale_ratio)
        h = int(rect.height() / self.scale_ratio)

        return x, y, w, h

    def add_roi_label(self, rect, coords, roi_name):
        text = f"{roi_name}\n{coords[0]},{coords[1]}\n{coords[2]},{coords[3]}"
        label_item = QGraphicsTextItem(text)
        # 修改label字体大小
        font = label_item.font()
        font.setPointSize(8)
        label_item.setFont(font)
        label_item.setDefaultTextColor(QColor(255, 255, 255))
        text_rect = label_item.boundingRect()
        center = rect.center()
        label_item.setPos(center.x() - text_rect.width() / 2, center.y() - text_rect.height() / 2)
        self.scene.addItem(label_item)
        return label_item

    def mousePressEvent(self, event):
        if self.image_item and event.button() == Qt.LeftButton:
            self.dragging = True
            self.start_point = self.mapToScene(event.pos())
            size = self.resized_image.shape
            # 强行转为int, 确保坐标按照像素点走
            self.start_point.setX(int(max(0, min(self.start_point.x(), size[1]))))
            self.start_point.setY(int(max(0, min(self.start_point.y(), size[0]))))

            # 创建新的ROI矩形（当前绘制）
            self.active_roi_rect = QRectF(self.start_point, self.start_point)
            self.active_roi_item = self.scene.addRect(
                self.active_roi_rect,
                QPen(Qt.red, 1),
                QBrush(QColor(255, 0, 0, 150)),
            )
        elif self.image_item and event.button() == Qt.RightButton:
            click_pos = self.mapToScene(event.pos())
            for item in reversed(self.roi_items):
                if item["rect"].contains(click_pos):
                    self.scene.removeItem(item["rect_item"])
                    self.scene.removeItem(item["label_item"])
                    self.roi_items.remove(item)
                    zoom_percent = int(self.zoom_factor * 100)
                    if self.roi_items:
                        x, y, w, h = self.roi_items[-1]["coords"]
                        self.status_label.setText(
                            f"已删除ROI | 剩余: {len(self.roi_items)} | 最后ROI: [X: {x}, Y: {y}, W: {w}, H: {h}] | 缩放: {zoom_percent}%"
                        )
                    else:
                        self.status_label.setText(f"已删除ROI | 缩放: {zoom_percent}%")
                    return

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

            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta_x)
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta_y)

            self.pan_start_x = event.x()
            self.pan_start_y = event.y()
        elif self.image_item and self.dragging:
            # 左键拖动选择ROI
            end_point = self.mapToScene(event.pos())
            size = self.resized_image.shape
            # 强行转为int, 确保坐标按照像素点走
            end_point.setX(int(max(0, min(end_point.x(), size[1]))))
            end_point.setY(int(max(0, min(end_point.y(), size[0]))))

            # 更新矩形
            self.active_roi_rect = QRectF(self.start_point, end_point).normalized()
            if self.active_roi_item:
                self.active_roi_item.setRect(self.active_roi_rect)

            # 更新状态
            if self.active_roi_rect:
                x, y, w, h = self.get_original_roi_from_rect(self.active_roi_rect)
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
            if self.active_roi_rect and self.active_roi_item:
                x, y, w, h = self.get_original_roi_from_rect(self.active_roi_rect)
                if w > 0 and h > 0:
                    # 提示用户输入ROI名称
                    default_name = "roi"
                    roi_name, ok = QInputDialog.getText(self, "ROI命名", "请输入ROI名称:", text=default_name)
                    roi_name = roi_name.strip() if ok else ""
                    if not roi_name:
                        roi_name = default_name

                    # 为ROI区域添加标签
                    label_item = self.add_roi_label(self.active_roi_rect, (x, y, w, h), roi_name)

                    # 记录roi
                    self.roi_items.append(
                        {
                            # 存储当前ROI的QRectF对象，方便后续删除时使用
                            "rect": self.active_roi_rect,
                            # 存储当前ROI的QGraphicsRectItem对象，方便后续删除时使用
                            "rect_item": self.active_roi_item,
                            # 存储当前ROI的标签项，方便后续删除时使用
                            "label_item": label_item,
                            # 存储原始图像中的ROI坐标
                            "coords": (x, y, w, h),
                            # 存储用户输入的ROI名称
                            "name": roi_name,
                            # 存储原始图像中的ROI数据
                            "data": self.origin_image[y : y + h, x : x + w],
                        }
                    )
                    zoom_percent = int(self.zoom_factor * 100)
                    self.status_label.setText(
                        f"选择完成: [X: {x}, Y: {y}, W: {w}, H: {h}] | 总数: {len(self.roi_items)} | 缩放: {zoom_percent}%"
                    )
                    print(f"选择的ROI (原始尺寸): X={x}, Y={y}, Width={w}, Height={h}")
                else:
                    self.scene.removeItem(self.active_roi_item)
                self.active_roi_item = None
                self.active_roi_rect = None
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
            if self.roi_items:
                x, y, w, h = self.roi_items[-1]["coords"]
                self.status_label.setText(
                    f"ROI: [X: {x}, Y: {y}, W: {w}, H: {h}] | 总数: {len(self.roi_items)} | 缩放: {zoom_percent}%"
                )
            else:
                self.status_label.setText(f"拖动鼠标选择ROI | 缩放: {zoom_percent}%")
        else:
            # 如果没有按Ctrl，使用默认滚动行为
            super().wheelEvent(event)

    def reset_roi(self):
        """重置当前ROI选择"""
        if self.active_roi_item:
            self.scene.removeItem(self.active_roi_item)
            self.active_roi_item = None
        for item in self.roi_items:
            self.scene.removeItem(item["rect_item"])
            self.scene.removeItem(item["label_item"])
        self.roi_items = []
        self.active_roi_rect = None
        self.status_label.setText("ROI已重置")


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

        # 导出标注图按钮
        self.btn_export_annotated = QPushButton("导出标注图")
        self.btn_export_annotated.clicked.connect(self.export_annotated_image)
        btn_layout.addWidget(self.btn_export_annotated)

        # 导出ROI按钮
        self.btn_export = QPushButton("导出ROI")
        self.btn_export.clicked.connect(self.export_roi)
        btn_layout.addWidget(self.btn_export)

        layout.addLayout(btn_layout)

        # 添加状态标签
        layout.addWidget(self.roi_selector.status_label)

    def open_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "打开图像", "", "图像文件 (*.png *.jpg *.jpeg *.bmp)")

        if file_path:
            # 重置ROI状态
            self.roi_selector.reset_roi()
            success = self.roi_selector.load_image(file_path)
            if success:
                self.roi_selector.status_label.setText("拖动鼠标选择ROI")
            else:
                self.roi_selector.status_label.setText("无法加载图像")
                # 确保清除无效图像
                self.roi_selector.origin_image = None
                self.roi_selector.image_path = None

    def export_roi(self):
        """处理导出ROI图像的操作"""
        if self.roi_selector.origin_image is None:
            QMessageBox.warning(self, "导出失败", "没有加载图像或没有选择ROI")
            return

        roi_list = self.roi_selector.roi_items
        if len(roi_list) == 0:
            QMessageBox.warning(self, "导出失败", "没有选择任何ROI")
            return

        try:
            # 获取保存目录
            save_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
            if not save_dir:
                return

            saved_paths = []
            img_height, img_width = self.roi_selector.origin_image.shape[:2]

            for item in roi_list:
                roi_img = item["data"]
                x, y, w, h = item["coords"]
                roi_name = item["name"]

                # 命名规范 resolution-ROI-name
                save_path = pathlib.Path(save_dir) / f"{img_width}x{img_height}-{roi_name}-{x}_{y}_{w}_{h}.png"
                cv2.imwrite(str(save_path), roi_img)

                saved_paths.append(str(save_path))

            QMessageBox.information(self, "导出成功", f"ROI图像已成功保存到:\n{save_dir}\n数量: {len(roi_list)}")

        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存图像时出错:\n{str(e)}")

    def export_annotated_image(self):
        """导出带ROI标注的整图"""
        if self.roi_selector.origin_image is None:
            QMessageBox.warning(self, "导出失败", "没有加载图像或没有选择ROI")
            return

        filePath, _ = QFileDialog.getSaveFileName(self, "保存图片", "", "PNG Files (*.png)")
        if not filePath:
            return

        # 获取场景的边界矩形
        scene = self.roi_selector.scene
        rect = scene.sceneRect()

        # 创建QImage
        image = QImage(int(rect.width()), int(rect.height()), QImage.Format_ARGB32)

        # 创建QPainter并渲染场景
        painter = QPainter(image)
        scene.render(painter, QRectF(image.rect()), rect)
        painter.end()

        # 保存图片
        image.save(filePath)
        QMessageBox.information(self, "导出成功", f"标注图已成功保存到:\n{filePath}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
