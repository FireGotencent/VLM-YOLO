"""
提示词模板模块
定义用于导航辅助的提示词模板
"""

# 系统提示词：导航助手角色
SYSTEM_PROMPT = """你是一位专业的盲人导航助手，名叫"视导"。你的职责是：

1. **安全第一**：始终优先考虑用户的人身安全
2. **简洁明了**：使用简短、清晰的语言，避免冗长的描述
3. **方位清晰**：使用"左侧"、"右侧"、"正前方"等明确的方位词
4. **距离估算**：提供大致的距离信息（如"约2米"、"很近"）
5. **行动建议**：给出具体可执行的建议（如"请向左偏移一步"）

请记住，用户看不见周围环境，你的描述是他们了解世界的唯一方式。"""


# 场景描述模板
SCENE_DESCRIPTION_TEMPLATE = """当前检测到以下物体：

{detections}

请根据这些信息，用简洁的语言为视障用户描述当前场景，并给出行走建议。
要求：
1. 优先提醒可能造成危险的物体
2. 说明物体的大致位置和距离
3. 给出具体的行动建议"""


# 障碍物警告模板
OBSTACLE_WARNING_TEMPLATE = """⚠️ 障碍物警告

检测到：{object_name}
位置：{position}
距离：约{distance}米

请立即给出简短的安全提醒（不超过20个字）。"""


# 路径建议模板
PATH_SUGGESTION_TEMPLATE = """当前路况：
- 左侧：{left_status}
- 正前方：{front_status}  
- 右侧：{right_status}

请分析当前路况，给出最安全的行走方向建议。"""


# 检测结果格式化
def format_detections(detections: list) -> str:
    """
    格式化检测结果为文本描述
    
    Args:
        detections: 检测结果列表
        
    Returns:
        str: 格式化后的文本
    """
    if not detections:
        return "未检测到任何物体"
    
    lines = []
    for i, det in enumerate(detections, 1):
        line = f"{i}. {det.get('name', '未知物体')}"
        if "position" in det:
            line += f" - {det['position']}"
        if "distance" in det:
            line += f" (约{det['distance']}米)"
        lines.append(line)
    
    return "\n".join(lines)


def build_scene_prompt(detections: list) -> str:
    """
    构建场景描述提示词
    
    Args:
        detections: 检测结果列表
        
    Returns:
        str: 完整的提示词
    """
    formatted = format_detections(detections)
    return SCENE_DESCRIPTION_TEMPLATE.format(detections=formatted)


def build_warning_prompt(
    object_name: str,
    position: str,
    distance: float
) -> str:
    """
    构建障碍物警告提示词
    
    Args:
        object_name: 物体名称
        position: 位置描述
        distance: 距离（米）
        
    Returns:
        str: 警告提示词
    """
    return OBSTACLE_WARNING_TEMPLATE.format(
        object_name=object_name,
        position=position,
        distance=distance
    )


def build_path_prompt(
    left_status: str = "畅通",
    front_status: str = "畅通",
    right_status: str = "畅通"
) -> str:
    """
    构建路径建议提示词
    
    Args:
        left_status: 左侧状态
        front_status: 正前方状态
        right_status: 右侧状态
        
    Returns:
        str: 路径建议提示词
    """
    return PATH_SUGGESTION_TEMPLATE.format(
        left_status=left_status,
        front_status=front_status,
        right_status=right_status
    )
