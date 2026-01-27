"""
深度估计模块（预留）
用于估计检测目标的距离
"""

from typing import Optional

import numpy as np

from src.utils.logger import get_logger

logger = get_logger()


class DepthEstimator:
    """深度估计器（占位实现）"""
    
    def __init__(self, method: str = "simple"):
        """
        初始化深度估计器
        
        Args:
            method: 估计方法 (simple/monocular/stereo)
        """
        self.method = method
        self._model = None
    
    def load(self) -> bool:
        """加载深度估计模型"""
        logger.info(f"深度估计器初始化 (方法: {self.method})")
        return True
    
    def estimate(
        self,
        frame: np.ndarray,
        bbox: tuple,
        class_name: str = ""
    ) -> Optional[float]:
        """
        估计目标距离
        
        基于简单的透视原理进行粗略估计：
        - 假设已知物体的典型尺寸
        - 根据边界框大小反推距离
        
        Args:
            frame: 输入图像
            bbox: 边界框 (x1, y1, x2, y2)
            class_name: 类别名称
            
        Returns:
            Optional[float]: 估计距离(米)，如果无法估计则返回 None
        """
        if self.method != "simple":
            logger.warning(f"方法 {self.method} 尚未实现，使用简单估计")
        
        # 典型物体高度（米）
        typical_heights = {
            "person": 1.7,
            "car": 1.5,
            "bicycle": 1.0,
            "motorcycle": 1.1,
            "bus": 3.0,
            "truck": 2.5,
            "dog": 0.5,
            "cat": 0.3,
            "chair": 0.8,
            "bench": 0.5,
        }
        
        typical_height = typical_heights.get(class_name, 1.0)
        
        # 计算边界框高度占图像高度的比例
        frame_height = frame.shape[0]
        x1, y1, x2, y2 = bbox
        bbox_height = y2 - y1
        height_ratio = bbox_height / frame_height
        
        if height_ratio < 0.01:
            return None
        
        # 简单估计：假设相机焦距和视场角
        # 这是一个非常粗略的估计
        focal_length_ratio = 1.5  # 经验值
        estimated_distance = (typical_height * focal_length_ratio) / height_ratio
        
        # 限制范围
        estimated_distance = max(0.5, min(20.0, estimated_distance))
        
        return round(estimated_distance, 1)
