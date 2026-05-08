"""
实验四：距离估算精度评估
使用前请先准备测试图片：
  data/distance_test/target_0.5m.jpg
  data/distance_test/target_1.0m.jpg
  data/distance_test/target_1.5m.jpg
  data/distance_test/target_2.0m.jpg
  data/distance_test/target_3.0m.jpg
运行: python scripts/eval_distance.py
"""
import statistics
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.detection.yolo_detector import YOLODetector

TEST_DIR = Path("data/distance_test")
TEST_CASES = [
    ("target_0.5m.jpg", 0.5),
    ("target_1.0m.jpg", 1.0),
    ("target_1.5m.jpg", 1.5),
    ("target_2.0m.jpg", 2.0),
    ("target_3.0m.jpg", 3.0),
]


def heuristic_distance(det, frame) -> float:
    h, w = frame.shape[:2]
    ratio = det.area / max(1, w * h)
    if ratio >= 0.20: return 0.8
    if ratio >= 0.10: return 1.2
    if ratio >= 0.05: return 2.0
    if ratio >= 0.02: return 3.0
    return 4.0


def main():
    detector = YOLODetector("yolo26n.pt", confidence=0.3)
    if not detector.load():
        print("模型加载失败")
        return

    print(f"{'实测(m)':<10} {'估算(m)':<10} {'绝对误差(m)':<14} {'相对误差(%)'}")
    print("-" * 50)

    errors = []
    for filename, real_dist in TEST_CASES:
        img_path = TEST_DIR / filename
        if not img_path.exists():
            print(f"{real_dist:<10.1f} {'图片不存在: ' + filename}")
            continue

        frame = cv2.imread(str(img_path))
        dets = detector.detect(frame)
        if not dets:
            print(f"{real_dist:<10.1f} {'未检测到目标'}")
            continue

        # 取置信度最高的目标
        top = max(dets, key=lambda d: d.confidence)
        est = heuristic_distance(top, frame)
        abs_err = abs(real_dist - est)
        rel_err = abs_err / real_dist * 100
        errors.append(rel_err)
        print(f"{real_dist:<10.1f} {est:<10.1f} {abs_err:<14.2f} {rel_err:.1f}%")

    if errors:
        print("-" * 50)
        print(f"{'均值':<10} {'—':<10} {'—':<14} {statistics.mean(errors):.1f}%")
        print(f"\n平均相对误差: {statistics.mean(errors):.1f}%")


if __name__ == "__main__":
    main()
