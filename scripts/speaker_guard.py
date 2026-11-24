#!/usr/bin/env python3
"""Repair only the verified MateBook speaker path after ALSA/PipeWire events."""
import argparse
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time

CARD = 'alsa_card.pci-0000_00_1f.3-platform-skl_hda_dsp_generic'


def find_verified_card(sound_root=Path('/sys/class/sound')):
    """Find the internal codec by ALSA ID, irrespective of enumeration order."""
    for card in sorted(sound_root.glob('card[0-9]*')):
        try:
            if (card / 'id').read_text().strip() != 'sofhdadsp':
                continue
            index = card.name[4:]
            if not index.isdigit():
                continue
            codec = sound_root / f'hwC{index}D0'
            if int((codec / 'vendor_id').read_text(), 0) != 0x14f11f87:
                continue
            if int((codec / 'subsystem_id').read_text(), 0) != 0x19e53298:
                continue
            return int(index)
        except (OSError, ValueError):
            continue
    return None


def run(*args):
    return subprocess.check_output(args, text=True, timeout=3, env={**os.environ, "LC_ALL": "C"})


def speaker_route_ready(objects):
    for obj in objects:
        info = obj.get("info") or {}
        props = info.get("props") or {}
        if props.get("device.name") != CARD:
            continue
        if props.get("api.alsa.soft-mixer") not in (True, "true"):
            return False
        return any(route.get("name") == "[Out] Speaker"
                   and route.get("direction") == "Output"
                   and route.get("props", {}).get("mute") is False
                   for route in info.get("params", {}).get("Route", []))
    return False


def controls_to_restore(mixer):
    result = []
    for block in mixer.split("Simple mixer control '")[1:]:
        name = block.split("'", 1)[0]
        if name not in ("Master", "Speaker", "Headphone"):
            continue
        states = re.findall(r"(?:Mono|Front Left|Front Right): Playback[^\n]*?\[(-?[0-9.]+)dB\] \[(on|off)\]", block)
        if states and any(float(gain) != 0.0 or state != "on" for gain, state in states):
            result.append(name)
    return result


def hardware():
    try:
        model = Path("/sys/class/dmi/id/product_name").read_text().strip()
    except OSError:
        return None
    return find_verified_card() if model == "HKFG-XX" else None


def inspect(index):
    objects = json.loads(run("pw-dump"))
    if not speaker_route_ready(objects):
        return "扬声器路由未就绪、已静音，或没有启用软件混音", []
    jack = run("amixer", "-c", "sofhdadsp", "cget", "iface=CARD,name='Headphone Jack'")
    if not re.search(r"(?m)^\s*:\s*values=off\s*$", jack):
        return "检测到实体耳机，或无法确认插孔状态", []
    mixer = run("amixer", "-c", "sofhdadsp")
    return "内置扬声器路由已就绪", controls_to_restore(mixer)


def repair_once():
    index = hardware()
    if index is None:
        return
    _, controls = inspect(index)
    for control in controls:
        # The desktop/app's software volume and mute are never changed here.
        run("amixer", "-c", "sofhdadsp", "sset", control, "0dB", "unmute")
    if controls:
        print(f"Restored internal speaker path on card{index}: {', '.join(controls)}; software volume preserved.", flush=True)


def watch():
    sel = selectors.DefaultSelector()
    children = {}
    decoder = json.JSONDecoder()
    pw_buffer = ""
    card_id = None
    pending = time.monotonic()
    fallback = time.monotonic() + 30
    next_connect = 0.0

    def schedule():
        nonlocal pending
        due = time.monotonic() + 0.2
        pending = min(pending, due) if pending is not None else due

    def connect(kind, argv):
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True, env={**os.environ, "LC_ALL": "C"})
        os.set_blocking(proc.stdout.fileno(), False)
        sel.register(proc.stdout, selectors.EVENT_READ, kind)
        children[kind] = proc

    def disconnect(kind):
        proc = children.pop(kind)
        sel.unregister(proc.stdout)
        proc.stdout.close()
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    try:
        print("Watching ALSA control and PipeWire route changes; fallback check every 30 seconds.", flush=True)
        while True:
            now = time.monotonic()
            if now >= next_connect:
                if "alsa" not in children:
                    connect("alsa", ["stdbuf", "-oL", "alsactl", "monitor", "hw:sofhdadsp"])
                    schedule()
                if "pipewire" not in children:
                    pw_buffer = ""
                    card_id = None
                    connect("pipewire", ["pw-dump", "--monitor"])
                    schedule()
                next_connect = now + 3
            if now >= fallback:
                schedule()
                fallback = now + 30
            if pending is not None and now >= pending:
                pending = None
                try:
                    repair_once()
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    print(f"Speaker check deferred: {type(error).__name__}", flush=True)
            delay = min(1.0, max(0.0, pending - time.monotonic())) if pending is not None else 1.0
            for key, _ in sel.select(delay):
                kind = key.data
                data = os.read(key.fileobj.fileno(), 65536)
                if not data:
                    disconnect(kind)
                    continue
                if kind == "alsa":
                    schedule()
                    continue
                pw_buffer += data.decode("utf-8", errors="replace")
                while True:
                    pw_buffer = pw_buffer.lstrip()
                    if not pw_buffer:
                        break
                    try:
                        batch, end = decoder.raw_decode(pw_buffer)
                    except ValueError:
                        break
                    pw_buffer = pw_buffer[end:]
                    if not isinstance(batch, list):
                        continue
                    for obj in batch:
                        if not isinstance(obj, dict):
                            continue
                        info = obj.get("info")
                        props = (info or {}).get("props", {})
                        if props.get("device.name") == CARD:
                            card_id = obj.get("id")
                            schedule()
                        elif card_id is not None and obj.get("id") == card_id:
                            schedule()
                            if info is None:
                                card_id = None
                if len(pw_buffer) > 8 * 1024 * 1024:
                    disconnect("pipewire")
                    pw_buffer = ""
    finally:
        for kind in list(children):
            disconnect(kind)
        sel.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["check", "diagnose", "once", "watch"])
    mode = parser.parse_args().mode
    index = hardware()
    if index is None:
        print("未匹配 HKFG-XX / sofhdadsp / SN6140 19e5:3298。")
        return 1
    if mode in ("check", "diagnose"):
        print(f"匹配内置声卡 card{index}（sofhdadsp / SN6140 / 19e5:3298）。")
    if mode == "diagnose":
        try:
            reason, controls = inspect(index)
            print(reason + "。")
            if controls:
                print("待恢复的播放控制项：" + ", ".join(controls))
            elif reason == "内置扬声器路由已就绪":
                print("受管播放控制项没有发现异常。实际出声请播放音频确认。")
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            print(f"无法获取路由或混音器状态：{error}")
            return 1
    if mode == "once":
        repair_once()
    if mode == "watch":
        watch()
    return 0


if __name__ == "__main__":
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        pass
