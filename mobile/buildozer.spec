[app]
title = VisionGuide
package.name = visionguide
package.domain = org.visionguide

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf

version = 0.2

requirements = python3,kivy,plyer,websockets,pillow,android

orientation = portrait

fullscreen = 0

# Android 权限 (运行时权限)
android.permissions = CAMERA,INTERNET,RECORD_AUDIO,ACCESS_NETWORK_STATE,WAKE_LOCK

# Android 特性 (注意: 新版 p4a 已移除 --feature 参数支持)
# 摄像头功能会通过 CAMERA 权限自动声明，无需手动指定
# android.features = android.hardware.camera,android.hardware.camera.autofocus

# Android 架构
android.archs = arm64-v8a

# Android API
android.api = 33
android.minapi = 21

# 接受 SDK 许可
android.accept_sdk_license = True

# 调试模式
android.debug = 1

[buildozer]
log_level = 2
warn_on_root = 1

