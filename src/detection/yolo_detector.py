"""
YOLO 目标检测模块
封装 YOLOv8 模型进行实时目标检测
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class Detection:
    """检测结果数据类"""
    class_id: int           # 类别ID
    class_name: str         # 类别名称
    confidence: float       # 置信度
    bbox: Tuple[int, int, int, int]  # 边界框 (x1, y1, x2, y2)
    center: Tuple[int, int]  # 中心点 (cx, cy)
    relative_position: str   # 相对位置描述 (左/中/右)
    
    @property
    def width(self) -> int:
        """边界框宽度"""
        return self.bbox[2] - self.bbox[0]
    
    @property
    def height(self) -> int:
        """边界框高度"""
        return self.bbox[3] - self.bbox[1]
    
    @property
    def area(self) -> int:
        """边界框面积"""
        return self.width * self.height


class YOLODetector:
    """YOLO 目标检测器"""
    
    # 中文类别名称映射
    CLASS_NAMES_ZH = {
        "person": "行人",
        "bicycle": "自行车",
        "car": "汽车",
        "motorcycle": "摩托车",
        "bus": "公交车",
        "truck": "卡车",
        "dog": "狗",
        "cat": "猫",
        "chair": "椅子",
        "bench": "长凳",
        "traffic light": "红绿灯",
        "stop sign": "停止标志",
        "fire hydrant": "消防栓",
        "backpack": "背包",
        "umbrella": "雨伞",
        "handbag": "手提包",
        "suitcase": "行李箱",
        "bottle": "瓶子",
        "cup": "杯子",
        "potted plant": "盆栽",
        "bed": "床",
        "dining table": "餐桌",
        "toilet": "马桶",
        "tv": "电视",
        "laptop": "笔记本电脑",
        "cell phone": "手机",
    }
    
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.5,
        iou_threshold: float = 0.45,
        device: str = "auto",
        target_classes: Optional[List[str]] = None
    ):
        """
        初始化检测器
        
        Args:
            model_path: 模型文件路径
            confidence: 置信度阈值
            iou_threshold: NMS IOU 阈值
            device: 推理设备 (auto/cpu/cuda:0)
            target_classes: 目标类别列表（为空则检测所有类别）
        """
        self.model_path = model_path
        self.confidence = confidence
        self.iou_threshold = iou_threshold
        self.device = device
        self.target_classes = target_classes or []
        
        self._model = None
        self._class_names: List[str] = []
    
    def load(self) -> bool:
        """
        加载模型
        
        Returns:
            bool: 是否成功加载
        """
        try:
            from ultralytics import YOLO
            
            logger.info(f"正在加载 YOLO 模型: {self.model_path}")
            self._model = YOLO(self.model_path)
            
            # 获取类别名称
            self._class_names = list(self._model.names.values())
            logger.info(f"模型加载成功，共 {len(self._class_names)} 个类别")
            
            return True
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False
    
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        执行目标检测
        
        Args:
            frame: 输入图像 (BGR 格式)
            
        Returns:
            List[Detection]: 检测结果列表
        """
        if self._model is None:
            logger.warning("模型未加载")
            return []
        
        try:
            # 执行推理
            results = self._model(
                frame,
                conf=self.confidence,
                iou=self.iou_threshold,
                device=self.device if self.device != "auto" else None,
                verbose=False
            )
            
            detections = []
            frame_height, frame_width = frame.shape[:2]
            
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                
                for box in boxes:
                    # 获取检测信息
                    class_id = int(box.cls[0])
                    class_name = self._class_names[class_id]
                    confidence = float(box.conf[0])
                    
                    # 过滤目标类别
                    if self.target_classes and class_name not in self.target_classes:
                        continue
                    
                    # 获取边界框
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    
                    # 计算相对位置
                    relative_position = self._get_relative_position(cx, frame_width)
                    
                    detection = Detection(
                        class_id=class_id,
                        class_name=class_name,
                        confidence=confidence,
                        bbox=(x1, y1, x2, y2),
                        center=(cx, cy),
                        relative_position=relative_position
                    )
                    detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"检测失败: {e}")
            return []
    
    def _get_relative_position(self, cx: int, frame_width: int) -> str:
        """
        计算相对位置
        
        Args:
            cx: 中心点 x 坐标
            frame_width: 图像宽度
            
        Returns:
            str: 位置描述 (左侧/正前方/右侧)
        """
        third = frame_width // 3
        if cx < third:
            return "左侧"
        elif cx > 2 * third:
            return "右侧"
        else:
            return "正前方"
    
    def get_class_name_zh(self, class_name: str) -> str:
        """
        获取中文类别名称
        
        Args:
            class_name: 英文类别名称
            
        Returns:
            str: 中文类别名称
        """
        return self.CLASS_NAMES_ZH.get(class_name, class_name)
    
    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[Detection],
        show_label: bool = True,
        show_confidence: bool = True
    ) -> np.ndarray:
        """
        在图像上绘制检测结果
        
        Args:
            frame: 输入图像
            detections: 检测结果列表
            show_label: 是否显示标签
            show_confidence: 是否显示置信度
            
        Returns:
            np.ndarray: 绘制后的图像
        """
        output = frame.copy()
        
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            
            # 绘制边界框
            color = (0, 255, 0)  # 绿色
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            
            # 绘制标签
            if show_label:
                label = self.get_class_name_zh(det.class_name)
                if show_confidence:
                    label = f"{label} {det.confidence:.2f}"
                
                # 计算标签位置
                (label_width, label_height), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                )
                
                cv2.rectangle(
                    output,
                    (x1, y1 - label_height - 10),
                    (x1 + label_width + 10, y1),
                    color,
                    -1
                )
                cv2.putText(
                    output,
                    label,
                    (x1 + 5, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 0),
                    2
                )
        
        return output
    
    @property
    def is_loaded(self) -> bool:
        """模型是否已加载"""
        return self._model is not None
    
    @property
    def class_names(self) -> List[str]:
        """获取类别名称列表"""
        return self._class_names.copy()
