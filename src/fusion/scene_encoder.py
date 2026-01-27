"""
场景信息编码模块
将检测结果编码为结构化场景描述
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from src.detection.yolo_detector import Detection, YOLODetector
from src.utils.logger import get_logger

logger = get_logger()


@dataclass
class SceneObject:
    """场景中的物体"""
    name: str               # 物体名称
    name_zh: str            # 中文名称
    position: str           # 位置描述
    distance: Optional[float]  # 估计距离
    confidence: float       # 置信度
    danger_level: int       # 危险等级 (0-3)


@dataclass
class SceneInfo:
    """场景信息"""
    objects: List[SceneObject]
    total_count: int
    danger_count: int
    left_clear: bool
    front_clear: bool
    right_clear: bool
    summary: str


class SceneEncoder:
    """场景信息编码器"""
    
    # 危险等级映射
    DANGER_LEVELS = {
        "person": 1,      # 行人 - 低危险
        "bicycle": 2,     # 自行车 - 中危险
        "car": 3,         # 汽车 - 高危险
        "motorcycle": 3,  # 摩托车 - 高危险
        "bus": 3,         # 公交车 - 高危险
        "truck": 3,       # 卡车 - 高危险
        "dog": 2,         # 狗 - 中危险
        "cat": 1,         # 猫 - 低危险
        "chair": 1,       # 椅子 - 低危险
        "bench": 1,       # 长凳 - 低危险
    }
    
    def __init__(self, detector: Optional[YOLODetector] = None):
        """
        初始化场景编码器
        
        Args:
            detector: YOLO 检测器实例（用于获取中文名称）
        """
        self._detector = detector
    
    def encode(
        self,
        detections: List[Detection],
        distances: Optional[Dict[int, float]] = None
    ) -> SceneInfo:
        """
        编码检测结果为场景信息
        
        Args:
            detections: 检测结果列表
            distances: 距离字典 {检测索引: 距离}
            
        Returns:
            SceneInfo: 场景信息
        """
        distances = distances or {}
        
        objects = []
        left_obstacles = []
        front_obstacles = []
        right_obstacles = []
        danger_count = 0
        
        for i, det in enumerate(detections):
            # 获取中文名称
            name_zh = det.class_name
            if self._detector:
                name_zh = self._detector.get_class_name_zh(det.class_name)
            
            # 获取距离
            distance = distances.get(i)
            
            # 获取危险等级
            danger_level = self.DANGER_LEVELS.get(det.class_name, 1)
            
            obj = SceneObject(
                name=det.class_name,
                name_zh=name_zh,
                position=det.relative_position,
                distance=distance,
                confidence=det.confidence,
                danger_level=danger_level
            )
            objects.append(obj)
            
            # 按方向统计
            if det.relative_position == "左侧":
                left_obstacles.append(obj)
            elif det.relative_position == "正前方":
                front_obstacles.append(obj)
            elif det.relative_position == "右侧":
                right_obstacles.append(obj)
            
            if danger_level >= 2:
                danger_count += 1
        
        # 判断各方向是否畅通
        left_clear = len(left_obstacles) == 0
        front_clear = len(front_obstacles) == 0
        right_clear = len(right_obstacles) == 0
        
        # 生成摘要
        summary = self._generate_summary(objects, left_clear, front_clear, right_clear)
        
        return SceneInfo(
            objects=objects,
            total_count=len(objects),
            danger_count=danger_count,
            left_clear=left_clear,
            front_clear=front_clear,
            right_clear=right_clear,
            summary=summary
        )
    
    def _generate_summary(
        self,
        objects: List[SceneObject],
        left_clear: bool,
        front_clear: bool,
        right_clear: bool
    ) -> str:
        """生成场景摘要"""
        if not objects:
            return "前方道路畅通，无障碍物。"
        
        # 按危险等级排序
        sorted_objs = sorted(objects, key=lambda x: x.danger_level, reverse=True)
        
        parts = []
        for obj in sorted_objs[:3]:  # 最多显示3个
            part = f"{obj.position}有{obj.name_zh}"
            if obj.distance:
                part += f"(约{obj.distance}米)"
            parts.append(part)
        
        summary = "、".join(parts)
        
        # 添加方向建议
        if front_clear:
            summary += "。正前方畅通。"
        elif left_clear:
            summary += "。建议向左避让。"
        elif right_clear:
            summary += "。建议向右避让。"
        else:
            summary += "。请谨慎前行。"
        
        return summary
    
    def to_dict(self, scene_info: SceneInfo) -> dict:
        """
        将场景信息转换为字典
        
        Args:
            scene_info: 场景信息
            
        Returns:
            dict: 字典格式
        """
        return {
            "objects": [
                {
                    "name": obj.name,
                    "name_zh": obj.name_zh,
                    "position": obj.position,
                    "distance": obj.distance,
                    "confidence": obj.confidence,
                    "danger_level": obj.danger_level
                }
                for obj in scene_info.objects
            ],
            "total_count": scene_info.total_count,
            "danger_count": scene_info.danger_count,
            "left_clear": scene_info.left_clear,
            "front_clear": scene_info.front_clear,
            "right_clear": scene_info.right_clear,
            "summary": scene_info.summary
        }
    
    def to_text(self, scene_info: SceneInfo) -> str:
        """
        将场景信息转换为文本描述
        
        Args:
            scene_info: 场景信息
            
        Returns:
            str: 文本描述
        """
        lines = [f"场景摘要: {scene_info.summary}", ""]
        
        if scene_info.objects:
            lines.append("检测到的物体:")
            for i, obj in enumerate(scene_info.objects, 1):
                line = f"  {i}. {obj.name_zh} - {obj.position}"
                if obj.distance:
                    line += f" (约{obj.distance}米)"
                line += f" [置信度: {obj.confidence:.2f}]"
                lines.append(line)
        
        lines.append("")
        lines.append(f"方向状态: 左侧{'畅通' if scene_info.left_clear else '有障碍'} | "
                    f"正前方{'畅通' if scene_info.front_clear else '有障碍'} | "
                    f"右侧{'畅通' if scene_info.right_clear else '有障碍'}")
        
        return "\n".join(lines)
