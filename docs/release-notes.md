## v0.1.0-preview

首版包含经验文档、一键检查并安装、只读诊断、安装与撤销三个分步入口。兼容范围为 MateBook 14s 2023 HKFG-XX / SN6140 19e5:3298、WirePlumber 0.4、PipeWire 与 systemd 桌面用户会话。实测外设为 WIKO HiGT Tube（RX 7600M XT）。同款机器用其他显卡坞时可先运行诊断。

下载并解压整个压缩包，执行 `bash scripts/matebook-speaker-fix.sh`。安装后守护器在登录的音频会话启动。本机旧版修复已听测其恢复效果。公开版已在同机通过只读核对和独立逻辑检查，首次安装请按文档验证扬声器、耳机、HDMI 和音量。
