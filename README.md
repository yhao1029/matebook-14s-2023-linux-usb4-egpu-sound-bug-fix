# MateBook 14s 2023 · USB4 外接显卡时内置扬声器无声

在 Zorin OS 18.1 上连接 **华为智选 WIKO HiGT Tube 显卡魔方（AMD Radeon RX 7600M XT）** 后，系统有时仍显示选中了内置扬声器，但机身不出声，电视的 HDMI 音频可以正常播放。本文记录如何定位、恢复并在以后每次登录时自动维护内置扬声器通路。

| 项目 | 实测环境 |
| --- | --- |
| 笔记本 | HUAWEI MateBook 14s 2023，HKFG-XX，Intel Core i9-13900H，32 GB |
| 外设 | WIKO HiGT Tube（RX 7600M XT），经 USB4 / 雷电 4 连接 |
| 内置音频 | Intel SOF，ALSA ID `sofhdadsp`，Conexant SN6140（`14f1:1f87`，子系统 `19e5:3298`） |
| Linux | Zorin OS 18.1，PipeWire、WirePlumber 0.4.17、systemd 用户会话 |

**自动修复按内置声卡匹配。** 脚本不会要求外接显卡一定是 RX 7600M XT，所以同一台笔记本换其他显卡坞，如果复现的是同一条扬声器通路问题，可以先跑诊断。其他 MateBook 型号、声卡子系统和 WirePlumber 0.5 暂未纳入自动安装。外设与故障相关是实测现象，根因尚未证实，部分排查中断开显卡后也观察过无声。

### 下载与使用

从 [Releases 下载整包](https://github.com/yhao1029/matebook-14s-2023-linux-usb4-egpu-sound-bug-fix/releases)，解压后用普通桌面用户运行：

```bash
bash scripts/matebook-speaker-fix.sh
```

选 `a` 可依次检查并安装。分步也可单独运行：

| 步骤 | 入口 | 作用 |
| --- | --- | --- |
| 1 | [01-diagnose.sh](scripts/01-diagnose.sh) | 只读检查声卡、软件混音、扬声器路由、耳机插孔和已安装服务 |
| 2 | [02-install.sh](scripts/02-install.sh) | 保存本机 ALSA 快照，安装规则和用户服务 |
| 3 | [03-uninstall.sh](scripts/03-uninstall.sh) | 移除本项目文件及登录自启，保留安装前快照 |

安装会短暂重启当前用户的 WirePlumber。之后守护服务随桌面音频启动，监听声卡和音频路由变化，并每 30 秒补查一次。用低音量播放确认出声，再测试系统音量、应用音量、静音和 HDMI 输出。遇到复发可再运行只读诊断。步骤和依据见[排查、手动安装及恢复](docs/troubleshooting.md)。
