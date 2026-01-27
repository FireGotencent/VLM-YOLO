# 使用 Google Colab 打包 Android APK

## 概述

由于 Buildozer 需要 Linux 环境，而 Windows 用户可能无法使用 WSL，本指南介绍如何使用免费的 Google Colab 来打包 Android APK。

---

## 步骤 1: 准备项目文件

将 `mobile/` 目录打包成 zip 文件上传到 Google Drive：

```
mobile/
├── main.py
├── websocket_client.py
├── tts_client.py
├── buildozer.spec
└── requirements.txt
```

---

## 步骤 2: 创建 Colab Notebook

访问 https://colab.research.google.com/ 并创建新 Notebook。

---

## 步骤 3: 运行以下代码

### Cell 1: 安装依赖

```python
# 安装 buildozer 和依赖
!pip install buildozer cython

# 安装系统依赖
!sudo apt-get update
!sudo apt-get install -y \
    python3-pip \
    build-essential \
    git \
    python3 \
    python3-dev \
    ffmpeg \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libportmidi-dev \
    libswscale-dev \
    libavformat-dev \
    libavcodec-dev \
    zlib1g-dev \
    libgstreamer1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    libgstreamer-plugins-bad1.0-0 \
    openjdk-17-jdk \
    unzip \
    autoconf \
    libtool \
    pkg-config \
    cmake

print("✅ 依赖安装完成")
```

### Cell 2: 挂载 Google Drive

```python
from google.colab import drive
drive.mount('/content/drive')
```

### Cell 3: 复制项目文件

```python
import os

# 假设你的 zip 文件在 Google Drive 的根目录
# 修改为你的实际路径
source_zip = '/content/drive/MyDrive/mobile.zip'

# 解压到 /content/
!unzip -o {source_zip} -d /content/

# 进入解压后的目录 (注意: zip 解压后会创建 mobile 文件夹)
work_dir = '/content/mobile'
os.chdir(work_dir)
print(f"当前目录: {os.getcwd()}")
!ls -la
```

### Cell 4: 初始化 Buildozer（首次）

```python
# 如果没有 buildozer.spec，先初始化
# !buildozer init

# 查看 spec 文件
!cat buildozer.spec
```

### Cell 5: 打包 APK

```python
# 打包 debug 版本 (首次约需 30-60 分钟)
# 会出现 "Buildozer is running as root" 警告，输入 y 继续
!buildozer android debug

print("✅ 打包完成！")
!ls -la bin/
```

### Cell 6: 下载 APK

```python
from google.colab import files

# 实际 APK 文件名包含架构信息
# 使用完整路径下载
files.download('/content/mobile/bin/visionguide-0.1-arm64-v8a-debug.apk')

# 或者复制到 Google Drive
# !cp /content/mobile/bin/*.apk /content/drive/MyDrive/
```

---

## 完整 Notebook 代码（优化版）

将以下代码复制到 Colab Notebook 中，按顺序运行每个 Cell。

### Cell 1: 初始化环境（约 2-5 分钟）

```python
#@title 🚀 Step 1: 安装依赖 (首次运行约 2-5 分钟)
%%capture install_output

import subprocess
import shutil

def is_installed(package):
    """检查包是否已安装"""
    return shutil.which(package) is not None

# 检查是否需要重新安装
need_install = not is_installed('buildozer')

if need_install:
    print("📦 正在安装依赖...")
    
    # 安装 Python 包
    !pip install -q buildozer cython==0.29.36
    
    # 安装系统依赖 (合并为单条命令加速)
    !sudo apt-get update -qq && sudo apt-get install -qq -y \
        python3-pip build-essential git python3-dev ffmpeg \
        libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
        libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev zlib1g-dev \
        libgstreamer1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
        openjdk-17-jdk unzip autoconf libtool pkg-config cmake 2>/dev/null
    
    print("✅ 依赖安装完成！")
else:
    print("✅ 依赖已存在，跳过安装")

# 验证安装
!buildozer version
```

### Cell 2: 挂载 Drive 并解压项目

```python
#@title 🔗 Step 2: 挂载 Google Drive 并解压项目
import os
from google.colab import drive

# 挂载 Drive
if not os.path.exists('/content/drive/MyDrive'):
    drive.mount('/content/drive')
    print("✅ Drive 已挂载")
else:
    print("✅ Drive 已挂载（跳过）")

# 配置路径 - 修改为你的实际文件名
ZIP_FILE = '/content/drive/MyDrive/mobile.zip'  #@param {type:"string"}
WORK_DIR = '/content/mobile'

# 检查文件是否存在
if not os.path.exists(ZIP_FILE):
    raise FileNotFoundError(f"❌ 找不到文件: {ZIP_FILE}\n请检查文件路径是否正确！")

# 解压（仅当目录不存在或强制刷新时）
if not os.path.exists(WORK_DIR) or not os.path.exists(f"{WORK_DIR}/main.py"):
    print(f"📁 正在解压 {ZIP_FILE}...")
    !rm -rf {WORK_DIR}
    !unzip -o -q {ZIP_FILE} -d /content/
    print("✅ 解压完成")
else:
    print("✅ 项目目录已存在（跳过解压）")

# 切换目录
os.chdir(WORK_DIR)
print(f"📂 当前目录: {os.getcwd()}")
!ls -la
```

### Cell 3: 打包 APK（约 30-60 分钟）

```python
#@title 🔨 Step 3: 打包 APK (首次约 30-60 分钟)
import os

# 确保在正确目录
os.chdir('/content/mobile')

# 设置环境变量，自动确认 root 警告
os.environ['BUILDOZER_WARN_ON_ROOT'] = '0'

# 清理旧构建（可选，取消注释以强制完全重建）
# !buildozer android clean

print("🔨 开始打包 APK...")
print("   首次运行需要下载 Android SDK/NDK，请耐心等待...")
print("   如果断开连接，重新运行此 Cell 即可从断点继续\n")

# 开始打包
!yes | buildozer android debug 2>&1 | tee build.log

# 检查结果
import glob
apk_files = glob.glob('/content/mobile/bin/*.apk')
if apk_files:
    print(f"\n✅ 打包成功！")
    for apk in apk_files:
        size_mb = os.path.getsize(apk) / (1024 * 1024)
        print(f"   📱 {os.path.basename(apk)} ({size_mb:.1f} MB)")
else:
    print("\n❌ 打包失败，请检查 build.log")
    print("   常见问题：查看上方日志中的 ERROR 信息")
```

### Cell 4: 下载 APK

```python
#@title 📥 Step 4: 下载 APK 到本地
import os
import glob
from google.colab import files

# 自动查找生成的 APK
apk_files = glob.glob('/content/mobile/bin/*.apk')

if not apk_files:
    print("❌ 没有找到 APK 文件，请先运行打包步骤")
else:
    # 下载最新的 APK
    latest_apk = max(apk_files, key=os.path.getctime)
    print(f"📥 正在下载: {os.path.basename(latest_apk)}")
    files.download(latest_apk)
    
    # 同时备份到 Drive
    backup_path = '/content/drive/MyDrive/VisionGuide_APK/'
    os.makedirs(backup_path, exist_ok=True)
    !cp {latest_apk} {backup_path}
    print(f"💾 已备份到 Drive: {backup_path}")
```

### Cell 5: 会话保活（可选）

```python
#@title ⏰ 保持会话活跃 (在打包时运行此 Cell 防止超时断开)
import time
from IPython.display import display, HTML
import threading

def keep_alive():
    """每 60 秒发送一次心跳"""
    while True:
        display(HTML('<script>console.log("keep alive")</script>'))
        time.sleep(60)

# 在后台运行
thread = threading.Thread(target=keep_alive, daemon=True)
thread.start()
print("✅ 会话保活已启动，可以继续其他操作")
```

---

## 🚀 一键执行版（整合所有步骤）

将以下代码复制到**单个 Cell** 中运行，全程自动化无需干预：

```python
#@title 🚀 VisionGuide APK 一键打包 (全自动)

# ==================== 配置区域 ====================
ZIP_FILE = '/content/drive/MyDrive/mobile.zip'  #@param {type:"string"}
WORK_DIR = '/content/mobile'
# ==================================================

import os, glob, shutil, threading, time
from IPython.display import display, HTML

# ========== 1. 会话保活 (后台运行) ==========
def keep_alive():
    while True:
        display(HTML('<script>console.log("keep alive")</script>'))
        time.sleep(60)
threading.Thread(target=keep_alive, daemon=True).start()

# ========== 2. 安装依赖 ==========
print("📦 [1/5] 安装依赖...")
if not shutil.which('buildozer'):
    get_ipython().system('pip install -q buildozer cython==0.29.36')
    get_ipython().system('sudo apt-get update -qq && sudo apt-get install -qq -y python3-pip build-essential git python3-dev ffmpeg libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev zlib1g-dev libgstreamer1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good openjdk-17-jdk unzip autoconf libtool pkg-config cmake 2>/dev/null')
    print("   ✅ 依赖安装完成")
else:
    print("   ✅ 依赖已存在")

# ========== 3. 挂载 Drive ==========
print("🔗 [2/5] 挂载 Google Drive...")
from google.colab import drive
if not os.path.exists('/content/drive/MyDrive'):
    drive.mount('/content/drive')
print("   ✅ Drive 已挂载")

# ========== 4. 解压项目 ==========
print("📁 [3/5] 解压项目文件...")
if not os.path.exists(ZIP_FILE):
    raise FileNotFoundError(f"❌ 找不到: {ZIP_FILE}")

if not os.path.exists(f"{WORK_DIR}/main.py"):
    get_ipython().system(f'rm -rf {WORK_DIR}')
    get_ipython().system(f'unzip -o -q {ZIP_FILE} -d /content/')
    print("   ✅ 解压完成")
else:
    print("   ✅ 项目已存在")

os.chdir(WORK_DIR)

# ========== 5. 打包 APK ==========
print("🔨 [4/5] 开始打包 APK (首次约 30-60 分钟)...")
os.environ['BUILDOZER_WARN_ON_ROOT'] = '0'
get_ipython().system('yes | buildozer android debug 2>&1 | tee build.log')

# ========== 6. 处理结果 ==========
print("📥 [5/5] 处理打包结果...")
apk_files = glob.glob(f'{WORK_DIR}/bin/*.apk')

if apk_files:
    latest_apk = max(apk_files, key=os.path.getctime)
    size_mb = os.path.getsize(latest_apk) / (1024 * 1024)
    
    # 备份到 Drive
    backup_dir = '/content/drive/MyDrive/VisionGuide_APK/'
    os.makedirs(backup_dir, exist_ok=True)
    get_ipython().system(f'cp {latest_apk} {backup_dir}')
    
    print(f"\n{'='*50}")
    print(f"✅ 打包成功！")
    print(f"📱 APK: {os.path.basename(latest_apk)} ({size_mb:.1f} MB)")
    print(f"💾 已备份到: {backup_dir}")
    print(f"{'='*50}")
    
    # 触发下载
    from google.colab import files
    files.download(latest_apk)
else:
    print("\n❌ 打包失败！请查看 build.log 中的错误信息")
    print("   运行以下命令查看错误: !tail -100 build.log")
```

---

## 注意事项

1. **首次打包耗时**: 约 30-60 分钟（下载 Android SDK/NDK）
2. **Colab 超时**: 免费版 Colab 90 分钟无操作会断开，建议保持页面活跃
3. **存储空间**: Colab 提供约 50GB 存储，足够打包使用
4. **保存工作**: 打包完成后及时下载 APK 或保存到 Drive

---

## 常见错误

### 错误: Java 版本不兼容
```bash
!sudo update-alternatives --set java /usr/lib/jvm/java-17-openjdk-amd64/bin/java
```

### 错误: 内存不足
在 buildozer.spec 中减少优化:
```
android.archs = arm64-v8a
```

### 错误: 下载超时
重新运行打包命令，buildozer 会从断点继续。
