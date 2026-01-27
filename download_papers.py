"""
批量下载开题报告参考文献 PDF
支持 arXiv、MDPI (Open Access)、CVF 等免费来源
"""

import os
import requests
import time
from pathlib import Path
from urllib.parse import urlparse

# 配置下载目录
DOWNLOAD_DIR = Path(__file__).parent / "papers"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# 请求头，模拟浏览器访问
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 参考文献列表：(编号, 文件名, PDF直接链接, 备注)
PAPERS = [
    (1, "Dorbala_2023_LLM_Zero_Shot_Object_Navigation.pdf",
     "https://arxiv.org/pdf/2303.03480.pdf",
     "Can an embodied agent find your 'cat-shaped mug'?"),
    
    (2, "Wang_2024_VisionGPT_Anomaly_Detection.pdf",
     "https://arxiv.org/pdf/2403.12415.pdf",
     "VisionGPT: LLM-Assisted Real-Time Anomaly Detection"),
    
    (3, "DeCurto_2023_Semantic_Scene_UAV.pdf",
     "https://www.mdpi.com/2504-446X/7/2/114/pdf",
     "Semantic scene understanding with LLMs on UAVs (MDPI Open Access)"),
    
    (4, "Ryu_2025_Words_to_Wheels.pdf",
     "https://arxiv.org/pdf/2410.10577.pdf",
     "Words to Wheels: Vision-Based Autonomous Driving"),
    
    # [5] SII 2024 会议论文 - 需要通过其他途径获取
    (5, "Zhu_2024_VLD_Service_Robot_Navigation.pdf",
     None,  # IEEE会议论文，需通过学校库或ResearchGate获取
     "Visual-language decision system (IEEE SII 2024) - 需手动下载"),
    
    (6, "Saxena_2025_UAV_VLN.pdf",
     "https://arxiv.org/pdf/2504.21432.pdf",
     "UAV-VLN: End-to-End Vision Language guided Navigation"),
    
    (7, "Song_2024_VLM_Social_Nav.pdf",
     "https://arxiv.org/pdf/2411.00927.pdf",
     "VLM-Social-Nav: Socially Aware Robot Navigation"),
    
    (8, "Redmon_2016_YOLO.pdf",
     "https://www.cv-foundation.org/openaccess/content_cvpr_2016/papers/Redmon_You_Only_Look_CVPR_2016_paper.pdf",
     "You Only Look Once: Unified, Real-Time Object Detection (CVPR 2016)"),
    
    (9, "Wang_2024_YOLOv9.pdf",
     "https://arxiv.org/pdf/2402.13616.pdf",
     "YOLOv9: Learning What You Want to Learn Using PGI"),
    
    (10, "Liu_2023_LLaVA_Visual_Instruction_Tuning.pdf",
     "https://arxiv.org/pdf/2304.08485.pdf",
     "Visual Instruction Tuning (LLaVA, NeurIPS 2023)"),
    
    (11, "OpenAI_2023_GPT4_Technical_Report.pdf",
     "https://arxiv.org/pdf/2303.08774.pdf",
     "GPT-4 Technical Report"),
    
    (12, "Radford_2021_CLIP.pdf",
     "https://arxiv.org/pdf/2103.00020.pdf",
     "Learning Transferable Visual Models From Natural Language Supervision"),
]


def download_pdf(url: str, filename: str, description: str) -> bool:
    """
    下载单个PDF文件
    
    Args:
        url: PDF下载链接
        filename: 保存的文件名
        description: 论文描述
    
    Returns:
        bool: 下载是否成功
    """
    filepath = DOWNLOAD_DIR / filename
    
    # 检查文件是否已存在
    if filepath.exists():
        print(f"  ⏭️  已存在，跳过: {filename}")
        return True
    
    try:
        print(f"  ⬇️  正在下载: {description[:50]}...")
        response = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        response.raise_for_status()
        
        # 检查是否为PDF
        content_type = response.headers.get('Content-Type', '')
        if 'pdf' not in content_type.lower() and not url.endswith('.pdf'):
            print(f"  ⚠️  警告: 返回内容可能不是PDF格式")
        
        # 写入文件
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = filepath.stat().st_size / 1024 / 1024  # MB
        print(f"  ✅  下载成功: {filename} ({file_size:.2f} MB)")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌  下载失败: {e}")
        return False


def main():
    """主函数：批量下载所有文献"""
    print("=" * 60)
    print("📚 开题报告参考文献批量下载工具")
    print("=" * 60)
    print(f"下载目录: {DOWNLOAD_DIR.absolute()}")
    print(f"总计文献: {len(PAPERS)} 篇")
    print("-" * 60)
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for idx, filename, url, description in PAPERS:
        print(f"\n[{idx}/12] {description[:45]}...")
        
        if url is None:
            print(f"  ⚠️  需手动下载 (IEEE/会议论文)")
            skip_count += 1
            continue
        
        if download_pdf(url, filename, description):
            success_count += 1
        else:
            fail_count += 1
        
        # 避免请求过于频繁
        time.sleep(1)
    
    # 打印统计结果
    print("\n" + "=" * 60)
    print("📊 下载统计")
    print("=" * 60)
    print(f"  ✅ 成功下载: {success_count} 篇")
    print(f"  ⏭️  已存在/跳过: {skip_count} 篇")
    print(f"  ❌ 下载失败: {fail_count} 篇")
    print(f"\n📁 文件保存位置: {DOWNLOAD_DIR.absolute()}")
    
    # 提示手动下载的文献
    if skip_count > 0:
        print("\n" + "-" * 60)
        print("⚠️  以下文献需要手动下载:")
        print("-" * 60)
        for idx, filename, url, description in PAPERS:
            if url is None:
                print(f"  [{idx}] {description}")
                print(f"      → 建议通过学校图书馆 IEEE Xplore 或 ResearchGate 获取")
    
    print("\n✨ 下载任务完成!")


if __name__ == "__main__":
    main()
