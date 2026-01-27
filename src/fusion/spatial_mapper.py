"""
空间位置映射模块
将像素坐标映射为空间位置描述
"""

from dataclasses import dataclass
from typing import List, Tuple

from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class SpatialPosition:
    """空间位置信息"""
    horizontal: str      # 水平位置: 左侧/左前/正前方/右前/右侧
    vertical: str        # 垂直位置: 上方/中间/下方
    zone: int            # 区域编号 (1-9)
    description: str     # 综合描述


class SpatialMapper:
    """空间位置映射器"""
    
    # 水平区域划分（9宫格）
    HORIZONTAL_ZONES = ["左侧", "左前方", "正前方", "右前方", "右侧"]
    VERTICAL_ZONES = ["上方", "中间", "下方"]
    
    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        """
        初始化映射器
        
        Args:
            frame_width: 图像宽度
            frame_height: 图像高度
        """
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # 计算区域边界
        self._update_boundaries()
    
    def _update_boundaries(self) -> None:
        """更新区域边界"""
        # 水平方向分为5个区域
        w = self.frame_width
        self.h_boundaries = [0, w * 0.15, w * 0.35, w * 0.65, w * 0.85, w]
        
        # 垂直方向分为3个区域
        h = self.frame_height
        self.v_boundaries = [0, h * 0.33, h * 0.67, h]
    
    def set_frame_size(self, width: int, height: int) -> None:
        """设置图像尺寸"""
        self.frame_width = width
        self.frame_height = height
        self._update_boundaries()
    
    def map_position(self, cx: int, cy: int) -> SpatialPosition:
        """
        映射像素坐标到空间位置
        
        Args:
            cx: 中心点 x 坐标
            cy: 中心点 y 坐标
            
        Returns:
            SpatialPosition: 空间位置信息
        """
        # 确定水平位置
        h_zone = 2  # 默认正前方
        for i, boundary in enumerate(self.h_boundaries[1:], 0):
            if cx < boundary:
                h_zone = i
                break
        horizontal = self.HORIZONTAL_ZONES[min(h_zone, len(self.HORIZONTAL_ZONES) - 1)]
        
        # 确定垂直位置
        v_zone = 1  # 默认中间
        for i, boundary in enumerate(self.v_boundaries[1:], 0):
            if cy < boundary:
                v_zone = i
                break
        vertical = self.VERTICAL_ZONES[min(v_zone, len(self.VERTICAL_ZONES) - 1)]
        
        # 计算区域编号（3x3 九宫格）
        h_simple = 0 if h_zone < 2 else (2 if h_zone > 2 else 1)
        zone = v_zone * 3 + h_simple + 1
        
        # 生成描述
        description = self._generate_description(horizontal, vertical)
        
        return SpatialPosition(
            horizontal=horizontal,
            vertical=vertical,
            zone=zone,
            description=description
        )
    
    def map_bbox(self, bbox: Tuple[int, int, int, int]) -> SpatialPosition:
        """
        映射边界框到空间位置
        
        Args:
            bbox: 边界框 (x1, y1, x2, y2)
            
        Returns:
            SpatialPosition: 空间位置信息
        """
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return self.map_position(cx, cy)
    
    def _generate_description(self, horizontal: str, vertical: str) -> str:
        """生成位置描述"""
        if horizontal == "正前方":
            if vertical == "中间":
                return "正前方"
            elif vertical == "上方":
                return "正前方偏上"
            else:
                return "正前方偏下"
        else:
            base = horizontal
            if vertical == "中间":
                return base
            elif vertical == "上方":
                return f"{base}偏上"
            else:
                return f"{base}偏下"
    
    def get_safe_direction(
        self,
        occupied_zones: List[int]
    ) -> str:
        """
        根据占用区域推荐安全方向
        
        Args:
            occupied_zones: 被占用的区域编号列表
            
        Returns:
            str: 安全方向建议
        """
        # 中间列区域: 2, 5, 8
        # 左侧列区域: 1, 4, 7
        # 右侧列区域: 3, 6, 9
        
        left_clear = all(z not in occupied_zones for z in [1, 4, 7])
        center_clear = all(z not in occupied_zones for z in [2, 5, 8])
        right_clear = all(z not in occupied_zones for z in [3, 6, 9])
        
        if center_clear:
            return "可以直行"
        elif left_clear and right_clear:
            return "两侧畅通，可向左或向右避让"
        elif left_clear:
            return "建议向左避让"
        elif right_clear:
            return "建议向右避让"
        else:
            return "前方拥挤，请谨慎前行或原地等待"
    
    def estimate_relative_size(
        self,
        bbox: Tuple[int, int, int, int]
    ) -> str:
        """
        估计物体的相对大小
        
        Args:
            bbox: 边界框
            
        Returns:
            str: 大小描述
        """
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        area = width * height
        frame_area = self.frame_width * self.frame_height
        
        ratio = area / frame_area
        
        if ratio > 0.25:
            return "非常大（很近）"
        elif ratio > 0.1:
            return "较大"
        elif ratio > 0.03:
            return "中等"
        elif ratio > 0.01:
            return "较小"
        else:
            return "很小（较远）"
