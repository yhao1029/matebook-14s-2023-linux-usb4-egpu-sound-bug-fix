# 排查、手动安装及恢复

## 先确认是不是同一种故障

1. 连接显卡，插着 HDMI 时在声音设置里分别选择内置扬声器和 HDMI。用低音量播放同一段声音并记录各自是否出声。
2. 用 `cat /proc/asound/cards`、`wpctl status` 查看设备。外接显卡的 HDMI 音频可能排在 `card0`，内置 SOF 声卡也可能变成 `card1`。用 ALSA ID `sofhdadsp` 识别内置卡。
3. 运行 `bash scripts/01-diagnose.sh`。确认机型、SN6140 与子系统都匹配，再检查软件混音、路由、静音和耳机插孔。安装前显示软件混音未开启属于预期结果。
4. 插拔前后分别记录路由和是否能听到声音。原排查曾看到 PipeWire 与 ALSA 播放流在运行、PCM 播放位置增长，但机身仍无声。流在运行只证明系统在送音频。
5. 本机恢复出声与 `Headphone` 控件解除静音有关。这个名字来自硬件混音器。在此机型上它也影响机身出声，所以应同时验证实体耳机插拔与内置扬声器，避免用一条无条件解除静音的命令。

上游的 [MateBook 14 SN6140 内核修正](https://git.zx2c4.com/linux-rng/commit/sound/hda?id=b57f5571a3e88febd38d60f9a9cefd8937a383ba) 匹配 `19e5:329e`，本机是 `19e5:3298`。公开脚本使用经过本机验证的用户态做法，不依赖把另一子系统的内核修正套用过来。

## 解决方案

本机使用 WirePlumber 0.4 的 ALSA 规则，为内置 SOF 设备启用 `api.alsa.soft-mixer`。随后仅当内置扬声器路由已启用、未静音且确认没有实体耳机时，守护脚本才恢复内置卡的 `Master`、`Speaker`、`Headphone` 播放控件到 0 dB 并解除硬件静音。系统、应用音量由软件混音管理。守护器按设备身份重新查找声卡，且只在实际需要时写入控制项。

Ubuntu 24.04 系若缺命令，可检查 `python3`、`alsa-utils`、`pipewire`、`wireplumber`。一键脚本依赖当前系统已有的桌面音频服务。使用了其他声音服务的系统应先确认兼容性。

### 手动部署

建议用 `bash scripts/02-install.sh`，它会查硬件、检查已经存在的配置并记录自身安装的文件。如果需要手动安装，在桌面用户终端完成以下步骤：

1. 运行 `python3 scripts/speaker_guard.py check` 和 `wireplumber --version`。确认匹配硬件和 WirePlumber 0.4。
2. 用 `alsactl -f "$HOME/matebook-speaker-before.state" store sofhdadsp` 备份。该文件留在本机。
3. 将 [WirePlumber 规则](../config/51-matebook-usb4-speaker.lua) 放入 `~/.config/wireplumber/main.lua.d/`，将 [守护脚本](../scripts/speaker_guard.py) 保存为 `~/.local/libexec/matebook-usb4-speaker.py`。
4. 将 [服务单元](../config/matebook-usb4-speaker.service) 放入 `~/.config/systemd/user/`，保留原文件名，并执行：

```bash
systemctl --user daemon-reload
systemctl --user enable matebook-usb4-speaker.service
systemctl --user restart wireplumber.service
systemctl --user status matebook-usb4-speaker.service
```

这属于 **登录后的桌面音频自启**。守护器启动时检查一次，后续监听音频设备和路由变化。旧版主机曾额外使用 WirePlumber 的 `ExecStartPost` 初始化，公开版由守护器处理启动检查，因此安装文件更少。已有旧版服务的电脑可以直接用公开诊断脚本，避免两套守护同时运行。

## 复发时

```bash
bash scripts/01-diagnose.sh
journalctl --user -u matebook-usb4-speaker.service -b -n 30 --no-pager
```

- 提示路由未就绪时先在声音设置选内置扬声器，解除系统静音后再查。
- 当前插着耳机时脚本会跳过硬件调整。拔掉耳机后重新选择扬声器。
- 插拔显卡后用 ALSA ID 检查内置卡，避免仍按安装时的数字编号访问。
- 有桌面声音却应用音量缺少变化时，先确认软件混音已生效，再测试另一应用。
- 诊断正常但仍无声时，分别记录有无外接显卡时的现象，并确认实际听到声音。需要共享日志时先检查其中的机器名、用户名或其他个人信息。

## 撤销

从发行包运行 `bash scripts/03-uninstall.sh`，确认后移除本项目文件，并重启当前用户的 WirePlumber。安装前的 ALSA 快照保留在 `${XDG_STATE_HOME:-$HOME/.local/state}/matebook-usb4-speaker/alsa-before.state`。如需恢复旧的混音状态，确认声卡还是同一张且没有在此后重新配置时，再用 `alsactl -f <快照路径> restore sofhdadsp`。它会恢复这张卡的全部已保存控制项。手动安装者应先禁用用户服务，再删除手动放入的三个文件，随后 reload 并重启 WirePlumber。
