# 自动化脚本说明

## onnxocr使用

### 安装onnx

```angular2html
pip install onnx==1.14.0
pip install onnxruntime-gpu==1.14.1
```

### 模型推理
```python
import cv2
model = ONNXPaddleOcr()

img = cv2.imread('./1.jpg')

# ocr识别结果
result = model.ocr(img)
print(result)

# 画box框
sav2Img(img, result)
```