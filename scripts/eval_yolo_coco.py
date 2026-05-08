"""
实验一：YOLO 目标检测性能评估（COCO val2017）
运行: python scripts/eval_yolo_coco.py
首次运行会自动下载 COCO val2017（约 1 GB）
"""
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
metrics = model.val(data="coco.yaml", split="val")

print("\n" + "=" * 40)
print("YOLO 检测性能汇总")
print("=" * 40)
print(f"mAP50:     {metrics.box.map50:.4f}")
print(f"mAP50-95:  {metrics.box.map:.4f}")
print(f"Precision: {metrics.box.mp:.4f}")
print(f"Recall:    {metrics.box.mr:.4f}")
print("=" * 40)
