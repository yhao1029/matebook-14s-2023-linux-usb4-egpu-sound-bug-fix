#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
config="${XDG_CONFIG_HOME:-$HOME/.config}"
rule="$config/wireplumber/main.lua.d/51-matebook-usb4-speaker.lua"
unit=matebook-usb4-speaker.service
unit_file="$config/systemd/user/$unit"
helper="$HOME/.local/libexec/matebook-usb4-speaker.py"
files=("$rule" "$unit_file" "$helper")
sources=("$root/config/51-matebook-usb4-speaker.lua" "$root/config/$unit" "$root/scripts/speaker_guard.py")
state="${XDG_STATE_HOME:-$HOME/.local/state}/matebook-usb4-speaker"

die() { printf '%s\n' "$*" >&2; exit 1; }
desktop_user() { [[ $EUID != 0 ]] || die '请从桌面会话用普通用户运行。'; }
require_tools() {
    local command
    for command in python3 amixer alsactl pw-dump wireplumber systemctl stdbuf; do
        command -v "$command" >/dev/null || die "缺少 $command。Ubuntu 可检查 python3、alsa-utils、pipewire、wireplumber。"
    done
}
diagnose() {
    require_tools
    printf 'WirePlumber：\n'
    wireplumber --version
    printf '\n本项目服务：\n'
    systemctl --user is-enabled "$unit" 2>/dev/null || true
    systemctl --user is-active "$unit" 2>/dev/null || true
    printf '\n声卡与路由检查：\n'
    python3 "$root/scripts/speaker_guard.py" diagnose
}
install_fix() {
    desktop_user
    require_tools
    python3 "$root/scripts/speaker_guard.py" check
    systemctl --user is-active --quiet wireplumber.service || die '请先登录运行 PipeWire/WirePlumber 的桌面。'
    wireplumber --version | grep -Eq 'Linked with libwireplumber 0\.4\.' ||
        die '自动安装仅验证 WirePlumber 0.4 系列。0.5 的配置格式不同。'
    for existing in matebook-speaker-guard.service; do
        if systemctl --user is-active --quiet "$existing" || systemctl --user is-enabled --quiet "$existing"; then
            die '检测到原有 MateBook 声音守护服务。请保留现有修复，可单独运行 diagnose。'
        fi
    done
    local target i
    for target in "${files[@]}" "$state"; do
        [[ ! -e "$target" && ! -L "$target" ]] || die "路径已存在：$target。请先检查原有配置。"
    done
    local choice
    read -r -p '将短暂重启当前桌面的音频服务并启用登录自启。输入 YES 安装：' choice
    [[ $choice == YES ]] || return 1
    umask 077
    mkdir -p -- "$(dirname -- "$state")"
    mkdir -- "$state"
    local -a written=()
    undo_install() {
        if [[ ${#written[@]} != 0 ]]; then
            systemctl --user disable --now "$unit" >/dev/null 2>&1 || true
            rm -f -- "${written[@]}"
            systemctl --user daemon-reload || true
            systemctl --user restart wireplumber.service || true
        fi
        rm -f -- "$state/alsa-before.state" "$state/installed.sha256"
        rmdir -- "$state" 2>/dev/null || true
    }
    trap 'undo_install' ERR
    trap 'undo_install; exit 130' INT
    trap 'undo_install; exit 143' TERM
    alsactl -f "$state/alsa-before.state" store sofhdadsp
    for i in "${!files[@]}"; do
        mkdir -p -- "$(dirname -- "${files[i]}")"
        written+=("${files[i]}")
        install -m 644 -- "${sources[i]}" "${files[i]}"
    done
    sha256sum -- "${files[@]}" > "$state/installed.sha256"
    systemctl --user daemon-reload
    systemctl --user enable "$unit"
    systemctl --user restart wireplumber.service
    systemctl --user is-active --quiet "$unit"
    trap - ERR INT TERM
    printf '已启用。请选内置扬声器，先用较低的系统音量播放，再检查音量和静音。\n'
}
uninstall_fix() {
    desktop_user
    if [[ ! -f "$state/installed.sha256" ]]; then die '找不到本脚本的安装记录。'; fi
    sha256sum -c --status "$state/installed.sha256" ||
        die '安装文件已修改或移动，请先查看安装记录后手动处理。'
    local choice
    read -r -p '移除本项目的自启、WirePlumber 规则和守护脚本？输入 YES：' choice
    [[ $choice == YES ]] || return 1
    systemctl --user disable --now "$unit"
    rm -- "${files[@]}"
    rm -- "$state/installed.sha256"
    systemctl --user daemon-reload
    systemctl --user restart wireplumber.service
    printf '已撤销本项目配置。安装前 ALSA 快照保存在：%s\n' "$state/alsa-before.state"
    printf '下次安装前，可把这个备份目录移动到其他位置留存。\n'
}
case "${1:-menu}" in
    all) diagnose; install_fix ;;
    diagnose) diagnose ;;
    install) install_fix ;;
    uninstall) uninstall_fix ;;
    menu)
        printf 'a 一键检查并安装\n1 只读诊断\n2 安装并启用登录自启\n3 撤销修复\n'
        read -r -p '选择：' choice
        case "$choice" in
            a) diagnose; install_fix ;;
            1) diagnose ;;
            2) install_fix ;;
            3) uninstall_fix ;;
            *) die '无效选项。' ;;
        esac ;;
    -h|--help) echo 'bash scripts/matebook-speaker-fix.sh [all|diagnose|install|uninstall]' ;;
    *) die '未知选项。' ;;
esac
