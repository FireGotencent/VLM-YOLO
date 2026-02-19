"""
导航建议生成模块
根据检测结果生成导航建议
"""

from typing import List, Optional

from src.detection.yolo_detector import Detection
from src.reasoning.llm_engine import LLMEngine
from src.reasoning.prompt_templates import (
    SYSTEM_PROMPT,
    build_scene_prompt,
    build_warning_prompt,
    build_path_prompt
)
from src.utils.config import get_config
from src.utils.logger import get_logger

logger = get_logger()


class NavigationAdvisor:
    """导航建议生成器"""
    
    def __init__(self, llm_engine: Optional[LLMEngine] = None):
        """
        初始化导航建议生成器
        
        Args:
            llm_engine: LLM 引擎实例，如不提供则自动创建
        """
        self._llm = llm_engine or LLMEngine()
        self._llm.set_system_prompt(SYSTEM_PROMPT)
        
        self._config = get_config().navigation
        
        logger.info("导航建议生成器初始化完成")
    
    def analyze_scene(self, detections: List[Detection]) -> str:
        """
        分析场景并生成描述
        
        Args:
            detections: 检测结果列表
            
        Returns:
            str: 场景描述和建议
        """
        if not detections:
            return "前方道路畅通，可以继续前行。"
        
        # 转换为字典格式
        det_list = []
        for det in detections:
            det_dict = {
                "name": det.class_name,
                "position": det.relative_position,
                "confidence": det.confidence
            }
            det_list.append(det_dict)
        
        prompt = build_scene_prompt(det_list)
        
        try:
            response = self._llm.chat(prompt, use_history=False)
            return response
        except Exception as e:
            logger.error(f"生成场景描述失败: {e}")
            return self._generate_fallback_description(detections)
    
    def generate_warning(
        self,
        detection: Detection,
        distance: Optional[float] = None,
        object_name: Optional[str] = None
    ) -> str:
        """
        生成障碍物警告
        
        Args:
            detection: 检测结果
            distance: 估计距离（米）
            
        Returns:
            str: 警告信息
        """
        distance = distance or 2.0  # 默认距离
        object_name = object_name or detection.class_name
        
        # 判断危险等级
        if distance <= self._config.danger_distance:
            urgency = "紧急"
        elif distance <= self._config.warning_distance:
            urgency = "注意"
        else:
            urgency = "提醒"
        
        prompt = build_warning_prompt(
            object_name=object_name,
            position=detection.relative_position,
            distance=distance
        )
        
        try:
            response = self._llm.chat(prompt, use_history=False)
            return f"【{urgency}】{response}"
        except Exception as e:
            logger.error(f"生成警告失败: {e}")
            return f"【{urgency}】{detection.relative_position}有{object_name}，请注意避让！"
    
    def suggest_path(self, detections: List[Detection]) -> str:
        """
        生成路径建议
        
        Args:
            detections: 检测结果列表
            
        Returns:
            str: 路径建议
        """
        # 统计各方向的障碍物
        left_obstacles = []
        front_obstacles = []
        right_obstacles = []
        
        for det in detections:
            if det.relative_position == "左侧":
                left_obstacles.append(det.class_name)
            elif det.relative_position == "正前方":
                front_obstacles.append(det.class_name)
            elif det.relative_position == "右侧":
                right_obstacles.append(det.class_name)
        
        # 生成状态描述
        left_status = "、".join(left_obstacles) if left_obstacles else "畅通"
        front_status = "、".join(front_obstacles) if front_obstacles else "畅通"
        right_status = "、".join(right_obstacles) if right_obstacles else "畅通"
        
        prompt = build_path_prompt(left_status, front_status, right_status)
        
        try:
            response = self._llm.chat(prompt, use_history=False)
            return response
        except Exception as e:
            logger.error(f"生成路径建议失败: {e}")
            return self._generate_fallback_path_suggestion(
                left_obstacles, front_obstacles, right_obstacles
            )
    
    def quick_alert(self, detections: List[Detection]) -> Optional[str]:
        """
        快速警报（不使用 LLM，直接生成）
        
        用于需要即时响应的场景
        
        Args:
            detections: 检测结果列表
            
        Returns:
            Optional[str]: 警报信息，如无需警报则返回 None
        """
        if not detections:
            return None
        
        # 按置信度排序，取最重要的
        sorted_dets = sorted(detections, key=lambda x: x.confidence, reverse=True)
        top_det = sorted_dets[0]
        
        # 生成简短警报
        alert = f"注意{top_det.relative_position}有{top_det.class_name}"
        
        if len(detections) > 1:
            alert += f"，共检测到{len(detections)}个物体"
        
        return alert
    
    def _generate_fallback_description(self, detections: List[Detection]) -> str:
        """生成备用描述（LLM 不可用时）"""
        if not detections:
            return "前方道路畅通。"
        
        desc_parts = []
        for det in detections:
            desc_parts.append(f"{det.relative_position}有{det.class_name}")
        
        return "检测到：" + "，".join(desc_parts) + "。请小心前行。"
    
    def _generate_fallback_path_suggestion(
        self,
        left: List[str],
        front: List[str],
        right: List[str]
    ) -> str:
        """生成备用路径建议"""
        if not front and not left and not right:
            return "三侧均畅通，可以继续前行。"
        
        if not front:
            return "正前方畅通，可以直行。"
        elif not left:
            return "建议向左侧移动后前行。"
        elif not right:
            return "建议向右侧移动后前行。"
        else:
            return "三侧均有障碍，请原地等待或寻求帮助。"
