import argparse
import sys
import os
import subprocess
import time
import shutil
from pathlib import Path
from typing import List, Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.prompt import Prompt, Confirm, IntPrompt
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .config import (
    ensure_dirs,
    load_config,
    save_config,
    STORAGE_DIR,
    CONFIG_DIR,
    send_notification,
    PRESETS,
    apply_preset,
    resolve_resolution,
    detect_aspect_ratio,
)
from .recorder import ScreenRecorder, ContinuousRecorder
from .storage import list_recordings, delete_recording, clean_all, sync_recordings, Recording
from . import __version__

console = Console() if HAS_RICH else None

SERVICE_NAME = "recorder.service"
USER_SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"
USER_SERVICE_PATH = USER_SYSTEMD_DIR / SERVICE_NAME

def print_msg(msg: str, style: str = "bold green"):
    if HAS_RICH and console:
        console.print(f"[{style}]{msg}[/{style}]")
    else:
        print(msg)

def print_error(msg: str):
    if HAS_RICH and console:
        console.print(f"[bold red]{msg}[/bold red]")
    else:
        print(f"Error: {msg}", file=sys.stderr)

def is_recording_active() -> bool:
    try:
        res = subprocess.run(["pgrep", "-f", "gpu-screen-recorder"], stdout=subprocess.PIPE, check=True)
        return bool(res.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def is_service_active() -> bool:
    try:
        res = subprocess.run(["systemctl", "--user", "is-active", "--quiet", SERVICE_NAME], check=False)
        return res.returncode == 0
    except Exception:
        return False

def is_service_enabled() -> bool:
    try:
        res = subprocess.run(["systemctl", "--user", "is-enabled", "--quiet", SERVICE_NAME], check=False)
        return res.returncode == 0
    except Exception:
        return False

def get_storage_stats():
    sync_recordings()
    recs = list_recordings(sync=False)
    total_bytes = sum(r.get_size_bytes() for r in recs)
    count = len(recs)
    
    # Format bytes
    bytes_val = float(total_bytes)
    unit = "B"
    for u in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024.0:
            unit = u
            break
        bytes_val /= 1024.0
    size_str = f"{bytes_val:.1f} {unit}"
    return count, size_str, total_bytes

def install_systemd_service():
    """Install or update the systemd user service unit with proper graphical-session binding"""
    USER_SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    recorder_bin = shutil.which("recorder") or str(Path.home() / ".local" / "bin" / "recorder")
    
    unit_content = f"""[Unit]
Description=Recorder CLI - Continuous Circular Screen & Audio Recorder
Documentation=https://github.com/KadirBerkpolat1/recorder-cli
After=graphical-session.target pipewire.service
BindsTo=graphical-session.target

[Service]
Type=simple
ExecStart={recorder_bin} daemon
Restart=on-failure
RestartSec=3
KillSignal=SIGTERM
TimeoutStopSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical-session.target
"""
    with open(USER_SERVICE_PATH, "w", encoding="utf-8") as f:
        f.write(unit_content)
    
    # Also remove legacy symlink from default.target.wants if present
    legacy_symlink = USER_SYSTEMD_DIR / "default.target.wants" / SERVICE_NAME
    if legacy_symlink.exists():
        try:
            legacy_symlink.unlink()
        except Exception:
            pass

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)

def cmd_daemon(args=None):
    """Runs continuous circular recording loop (for systemd or background process)"""
    ensure_dirs()
    continuous = ContinuousRecorder()
    continuous.run()

def cmd_record(args=None):
    ensure_dirs()
    if args:
        cfg = load_config()
        changed = False
        if getattr(args, "preset", None):
            apply_preset(args.preset)
            changed = False
        else:
            if getattr(args, "resolution", None):
                cfg["resolution"] = args.resolution
                cfg["preset"] = "custom"
                changed = True
            if getattr(args, "fps", None):
                cfg["fps"] = args.fps
                cfg["preset"] = "custom"
                changed = True
            if getattr(args, "quality", None):
                cfg["quality"] = args.quality
                cfg["preset"] = "custom"
                changed = True
            if getattr(args, "codec", None):
                cfg["codec"] = args.codec
                cfg["preset"] = "custom"
                changed = True
            if changed:
                save_config(cfg)

    if is_recording_active() or is_service_active():
        print_msg("Recording is already running!", style="bold yellow")
        return
    # If systemd service file exists, start via systemd user service
    if USER_SERVICE_PATH.exists():
        print_msg("Starting recording via systemd service...", style="cyan")
        subprocess.run(["systemctl", "--user", "start", SERVICE_NAME], check=False)
        time.sleep(1.0)
        if is_recording_active():
            print_msg("✓ Recording started successfully via systemd.", style="bold green")
            return

    # Fallback to background daemon
    print_msg("Starting recording in background daemon...", style="cyan")
    recorder_bin = shutil.which("recorder") or "recorder"
    subprocess.Popen(
        [recorder_bin, "daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    time.sleep(1.0)
    if is_recording_active():
        print_msg("✓ Recording started.", style="bold green")
    else:
        print_error("Failed to start recorder process. Check system logs.")

def cmd_stop(args=None):
    stopped_anything = False
    
    # 1. Stop systemd service if active
    if is_service_active():
        print_msg("Stopping systemd recording service...", style="cyan")
        subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME], check=False)
        stopped_anything = True

    # 2. If standalone daemon/gpu-screen-recorder is running, send SIGINT for clean MP4 save
    if is_recording_active():
        try:
            subprocess.run(["pkill", "-2", "-f", "gpu-screen-recorder"], check=True)
            stopped_anything = True
        except subprocess.CalledProcessError:
            pass

    if stopped_anything:
        time.sleep(0.5)
        sync_recordings()
        print_msg("✓ Recording stopped and latest video saved cleanly.", style="bold green")
        send_notification("Recording Stopped", "Session finished and video finalized.")
    else:
        print_msg("No active recording process found.", style="bold yellow")

def cmd_status(args=None):
    active = is_service_active()
    enabled = is_service_enabled()
    rec_active = is_recording_active()
    count, size_str, _ = get_storage_stats()
    cfg = load_config()

    preset_key = cfg.get("preset", "custom")
    preset_name = PRESETS.get(preset_key, {}).get("name", "Özel (Custom)")
    res_str = cfg.get("resolution", "native")
    res_resolved = resolve_resolution(res_str)
    res_display = f"{res_str.upper()} ({res_resolved})" if res_resolved and res_str != res_resolved else (res_resolved or "Native (1:1 Ekran)")

    if HAS_RICH and console:
        table = Table(title="🎥 Recorder CLI Status", show_header=False, box=None)
        table.add_column("Key", style="bold cyan", width=22)
        table.add_column("Value", style="bold")

        table.add_row(
            "Screen Recording",
            "[green]● RECORDING[/green]" if rec_active else "[red]○ IDLE[/red]"
        )
        table.add_row(
            "Systemd Service",
            "[green]Active (Running)[/green]" if active else "[dim]Inactive[/dim]"
        )
        table.add_row(
            "Boot Autostart",
            "[green]Enabled[/green]" if enabled else "[yellow]Disabled[/yellow]"
        )
        table.add_row("Aktif Profil", f"[yellow]{preset_name}[/yellow]")
        table.add_row("Çözünürlük", f"[bold]{res_display}[/bold]")
        table.add_row("Hardware Codec", f"[magenta]{cfg.get('codec', 'hevc').upper()}[/magenta] (VAAPI/Hardware)")
        table.add_row("Framerate / Quality", f"{cfg.get('fps', 60)} FPS / {cfg.get('quality', 'very_high')}")
        table.add_row("Target Screen", f"{cfg.get('monitor', 'screen')}")
        table.add_row("Saved Videos", f"{count} / {cfg.get('max_recordings', 5)} files ({size_str})")
        table.add_row("Storage Directory", f"{STORAGE_DIR}")
        console.print(Panel(table, border_style="cyan", expand=False))
    else:
        print(f"Screen Recording : {'🟢 RECORDING' if rec_active else '🔴 IDLE'}")
        print(f"Service Active   : {'🟢 YES' if active else '🔴 NO'}")
        print(f"Auto-start (Boot): {'🟢 ENABLED' if enabled else '⚪ DISABLED'}")
        print(f"Profil           : {preset_name}")
        print(f"Çözünürlük       : {res_display}")
        print(f"Codec            : {cfg.get('codec', 'hevc').upper()} ({cfg.get('fps', 60)} FPS)")
        print(f"Saved Recordings : {count} files ({size_str})")

def cmd_profile(args=None):
    name = getattr(args, "name", None) if args else None
    if not name:
        cfg = load_config()
        current_preset = cfg.get("preset", "custom")
        res_str = cfg.get("resolution", "native")
        res_resolved = resolve_resolution(res_str)
        res_display = f"{res_str.upper()} ({res_resolved})" if res_resolved and res_str != res_resolved else (res_resolved or "Native (1:1 Ekran)")

        if HAS_RICH and console:
            table = Table(title="🎯 Recorder CLI Kalite ve Performans Profilleri", box=None)
            table.add_column("Kod", style="bold cyan", width=14)
            table.add_column("Profil", style="bold yellow", width=26)
            table.add_column("Açıklama", style="white")
            table.add_column("Durum", style="bold green", width=10)

            for key, p in PRESETS.items():
                is_cur = "● AKTİF" if current_preset == key else ""
                table.add_row(key, p["name"], p["desc"], f"[green]{is_cur}[/green]" if is_cur else "")

            console.print(Panel(table, border_style="cyan", expand=False))
            console.print(f"\n[dim]Mevcut: [bold]{res_display}[/bold] | FPS: [bold]{cfg.get('fps')}[/bold] | Kalite: [bold]{cfg.get('quality')}[/bold][/dim]")
            console.print("\n[cyan]Profil uygulamak için:[/cyan] [yellow]recorder profile <kod>[/yellow] (örn: [bold]recorder profile performance[/bold])")
        else:
            print("=== Recorder CLI Profilleri ===")
            for key, p in PRESETS.items():
                mark = " (AKTİF)" if current_preset == key else ""
                print(f"- {key:14} : {p['name']} - {p['desc']}{mark}")
            print(f"\nMevcut: {res_display} | FPS: {cfg.get('fps')} | Kalite: {cfg.get('quality')}")
            print("Kullanım: recorder profile <kod> (örn: recorder profile performance)")
        return

    name = name.lower().strip()
    if name not in PRESETS:
        print_error(f"Geçersiz profil: '{name}'. Mevcut profiller: {', '.join(PRESETS.keys())}")
        return

    if apply_preset(name):
        cfg = load_config()
        res_resolved = resolve_resolution(cfg.get("resolution")) or "Native (1:1)"
        p_name = PRESETS[name]["name"]
        print_msg(f"✓ Profil uygulandı: {p_name}", style="bold green")
        print_msg(f"  → Çözünürlük: {res_resolved} | FPS: {cfg.get('fps')} | Kalite: {cfg.get('quality')} | Codec: {cfg.get('codec').upper()}", style="cyan")

        if is_service_active():
            subprocess.run(["systemctl", "--user", "restart", SERVICE_NAME], check=False)
            print_msg("✓ Arka plan kayıt servisi yeni profille anında güncellendi.", style="bold green")
def cmd_service(args):
    action = args.action.lower()
    install_systemd_service()

    if action == "enable":
        subprocess.run(["systemctl", "--user", "enable", "--now", SERVICE_NAME], check=False)
        print_msg("✓ Systemd servisi etkinleştirildi ve başlatıldı (Masaüstü her açıldığında arka planda kayıt alacak).")
    elif action == "disable":
        subprocess.run(["systemctl", "--user", "disable", "--now", SERVICE_NAME], check=False)
        print_msg("✓ Systemd servisi devre dışı bırakıldı ve durduruldu.")
    elif action == "start":
        subprocess.run(["systemctl", "--user", "start", SERVICE_NAME], check=False)
        print_msg("✓ Systemd servisi başlatıldı.")
    elif action == "stop":
        subprocess.run(["systemctl", "--user", "stop", SERVICE_NAME], check=False)
        print_msg("✓ Systemd servisi durduruldu (Kayıt kaydedildi).")
    elif action == "status":
        cmd_status()
    elif action == "install":
        print_msg("✓ Systemd user unit kurulu ve daemon güncellendi.")

def cmd_list(args=None):
    recordings = list_recordings(sync=True)
    if not recordings:
        print_msg("Henüz kaydedilmiş video yok.", style="yellow")
        return recordings

    if HAS_RICH and console:
        table = Table(title="🎞️ Kaydedilen Videolar", border_style="cyan")
        table.add_column("#", justify="center", style="bold cyan", width=4)
        table.add_column("Tarih", justify="center", style="white", width=12)
        table.add_column("Zaman Aralığı", justify="center", style="green", width=14)
        table.add_column("Süre", justify="center", style="yellow", width=10)
        table.add_column("Boyut", justify="right", style="magenta", width=10)
        table.add_column("Dosya Adı", justify="left", style="dim white")

        for i, rec in enumerate(recordings, 1):
            date_part = rec.start_time.split('_')[0] if '_' in rec.start_time else rec.start_time
            time_range = ""
            if '_' in rec.start_time:
                start_t = rec.start_time.split('_')[1].replace('-', ':')[:5]
                end_t = rec.end_time.replace('-', ':') if rec.end_time else "..."
                time_range = f"{start_t} - {end_t}"
            dur = f"{rec.duration_sec}s" if rec.duration_sec is not None else "..."
            size = rec.get_formatted_size()
            table.add_row(str(i), date_part, time_range, dur, size, rec.get_display_name())

        console.print(table)
    else:
        print(f"{'#':<3} | {'Date':<10} | {'Time Range':<13} | {'Duration':<8} | {'Size':<9} | {'File'}")
        print("-" * 80)
        for i, rec in enumerate(recordings, 1):
            date_part = rec.start_time.split('_')[0] if '_' in rec.start_time else rec.start_time
            time_range = ""
            if '_' in rec.start_time:
                start_t = rec.start_time.split('_')[1].replace('-', ':')[:5]
                end_t = rec.end_time.replace('-', ':') if rec.end_time else "..."
                time_range = f"{start_t}-{end_t}"
            dur = f"{rec.duration_sec}s" if rec.duration_sec is not None else "..."
            size = rec.get_formatted_size()
            print(f"{i:<3} | {date_part:<10} | {time_range:<13} | {dur:<8} | {size:<9} | {rec.get_display_name()}")
    
    return recordings

def cmd_play(args):
    recordings = list_recordings(sync=True)
    if not recordings:
        print_msg("Oynatılacak kayıt bulunamadı.", style="yellow")
        return
    
    idx = args.index if hasattr(args, "index") and args.index else 1
    if 1 <= idx <= len(recordings):
        rec = recordings[idx - 1]
        filepath = rec.get_path()
        print_msg(f"Oynatılıyor: {rec.get_display_name()}", style="cyan")
        if shutil.which("mpv"):
            subprocess.Popen(["mpv", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", str(filepath)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print_error(f"Kayıt #{idx} bulunamadı.")

def cmd_open(args=None):
    ensure_dirs()
    print_msg(f"Kayıt klasörü açılıyor: {STORAGE_DIR}", style="cyan")
    subprocess.Popen(["xdg-open", str(STORAGE_DIR)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def cmd_delete(args):
    if delete_recording(args.index - 1):
        print_msg(f"✓ #{args.index} numaralı kayıt silindi.", style="green")
    else:
        print_error(f"Kayıt #{args.index} bulunamadı.")

def cmd_clean(args=None):
    confirmed = False
    if HAS_RICH and console:
        confirmed = Confirm.ask("[bold red]Tüm kayıtları silmek istediğine emin misin?[/bold red]")
    else:
        ans = input("Tüm kayıtları silmek istediğinize emin misiniz? [y/N] ")
        confirmed = ans.lower() == "y"
        
    if confirmed:
        count = clean_all()
        print_msg(f"✓ {count} adet kayıt temizlendi.", style="green")
    else:
        print_msg("İşlem iptal edildi.", style="dim")

def interactive_settings():
    while True:
        config = load_config()
        preset_key = config.get("preset", "custom")
        preset_name = PRESETS.get(preset_key, {}).get("name", "Özel (Custom)")
        res_str = config.get("resolution", "native")
        res_resolved = resolve_resolution(res_str)
        res_display = f"{res_str.upper()} ({res_resolved})" if res_resolved and res_str != res_resolved else (res_resolved or "Native (1:1 Ekran)")

        if HAS_RICH and console:
            console.clear()
            table = Table(title="⚙️ Ayarlar", show_header=False, box=None)
            table.add_column("No", style="bold cyan", width=4)
            table.add_column("Ayar", style="bold", width=26)
            table.add_column("Değer", style="yellow")

            table.add_row("1", "🎯 Hazır Profil (Preset)", f"[bold green]{preset_name}[/bold green]")
            table.add_row("2", "📐 Çözünürlük", f"[bold cyan]{res_display}[/bold cyan]")
            table.add_row("3", "FPS (Kare Hızı)", f"{config.get('fps', 60)} fps")
            table.add_row("4", "Kayıt Kalitesi", f"{config.get('quality', 'very_high')}")
            table.add_row("5", "Video Codec", f"{config.get('codec', 'hevc').upper()} (hevc, av1, h264)")
            table.add_row("6", "Segment Süresi", f"{config.get('max_duration_sec', 1800) // 60} dakika")
            table.add_row("7", "Maksimum Video Sayısı", f"{config.get('max_recordings', 5)} adet")
            table.add_row("8", "Mikrofon Kaydı", "Açık" if config.get("record_mic", True) else "Kapalı")
            table.add_row("9", "Masaüstü Bildirimleri", "Açık" if config.get("notifications", True) else "Kapalı")
            table.add_row("10", "Geri Dön", "")
            console.print(Panel(table, border_style="cyan", expand=False))
            
            choice = Prompt.ask("\nSeçiminiz", choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"], default="10")
        else:
            print('\033c', end='')
            print("=== Ayarlar ===")
            print(f"1. Hazır Profil      : {preset_name}")
            print(f"2. Çözünürlük        : {res_display}")
            print(f"3. FPS               : {config.get('fps', 60)}")
            print(f"4. Kalite            : {config.get('quality', 'very_high')}")
            print(f"5. Codec             : {config.get('codec', 'hevc').upper()}")
            print(f"6. Segment Süresi    : {config.get('max_duration_sec', 1800) // 60} dk")
            print(f"7. Maks Kayıt Sayısı : {config.get('max_recordings', 5)}")
            print(f"8. Mikrofon Kaydı    : {'Açık' if config.get('record_mic', True) else 'Kapalı'}")
            print(f"9. Bildirimler       : {'Açık' if config.get('notifications', True) else 'Kapalı'}")
            print("10. Geri Dön")
            choice = input("\nSeçim: ").strip()

        if choice == "1":
            p_keys = list(PRESETS.keys())
            if HAS_RICH and console:
                console.print("\n[bold cyan]Kullanılabilir Hazır Profiller:[/bold cyan]")
                for i, k in enumerate(p_keys, 1):
                    console.print(f"  [bold yellow]{i}.[/bold yellow] {PRESETS[k]['name']} - [dim]{PRESETS[k]['desc']}[/dim]")
                console.print(f"  [bold yellow]{len(p_keys)+1}.[/bold yellow] İptal")
                p_choice = Prompt.ask("Profil seçin", choices=[str(x) for x in range(1, len(p_keys)+2)], default=str(len(p_keys)+1))
            else:
                for i, k in enumerate(p_keys, 1):
                    print(f"  {i}. {PRESETS[k]['name']} - {PRESETS[k]['desc']}")
                print(f"  {len(p_keys)+1}. İptal")
                p_choice = input("Seçim: ").strip()

            if p_choice.isdigit() and 1 <= int(p_choice) <= len(p_keys):
                apply_preset(p_keys[int(p_choice)-1])
                if is_service_active():
                    subprocess.run(["systemctl", "--user", "restart", SERVICE_NAME], check=False)
                    print_msg("✓ Arka plan kayıt servisi yeni profille anında güncellendi.", style="bold green")

        elif choice == "2":
            res_options = [
                ("native", "Native (Orijinal 1:1 Ekran Çözünürlüğü)"),
                ("1080p", "1080p (Full HD - 1920x1080 veya 1920x1200)"),
                ("1440p", "1440p / 2K (2560x1440 veya 2560x1600)"),
                ("4k", "4K (3840x2160 veya 3840x2400)"),
                ("720p", "720p (HD - 1280x720 veya 1280x800)"),
                ("custom", "Özel Çözünürlük Gir (WxH)"),
            ]
            if HAS_RICH and console:
                console.print("\n[bold cyan]Çözünürlük Seçenekleri:[/bold cyan]")
                for i, (val, desc) in enumerate(res_options, 1):
                    console.print(f"  [bold yellow]{i}.[/bold yellow] {desc}")
                console.print(f"  [bold yellow]{len(res_options)+1}.[/bold yellow] İptal")
                r_choice = Prompt.ask("Çözünürlük seçin", choices=[str(x) for x in range(1, len(res_options)+2)], default="1")
            else:
                for i, (val, desc) in enumerate(res_options, 1):
                    print(f"  {i}. {desc}")
                print(f"  {len(res_options)+1}. İptal")
                r_choice = input("Seçim: ").strip()

            if r_choice.isdigit() and 1 <= int(r_choice) <= len(res_options):
                val = res_options[int(r_choice)-1][0]
                if val == "custom":
                    val = (Prompt.ask("Çözünürlük (GenişlikxYükseklik, örn: 1600x900)") if (HAS_RICH and console) else input("Çözünürlük (WxH örn: 1600x900): ").strip())
                config["resolution"] = val
                config["preset"] = "custom"
                save_config(config)
                if is_service_active():
                    subprocess.run(["systemctl", "--user", "restart", SERVICE_NAME], check=False)
                    print_msg("✓ Arka plan kayıt servisi yeni çözünürlükle anında güncellendi.", style="bold green")

        elif choice == "3":
            if HAS_RICH and console:
                fps = Prompt.ask("FPS seçin", choices=["30", "60", "120", "144"], default=str(config.get("fps", 60)))
            else:
                fps = input("FPS (30 / 60 / 120 / 144): ").strip()
            if fps.isdigit():
                config["fps"] = int(fps)
                config["preset"] = "custom"
                save_config(config)
                if is_service_active():
                    subprocess.run(["systemctl", "--user", "restart", SERVICE_NAME], check=False)
        elif choice == "4":
            if HAS_RICH and console:
                quality = Prompt.ask("Kalite seçin", choices=["ultra", "very_high", "high", "medium"], default=config.get("quality", "very_high"))
            else:
                quality = input("Kalite (ultra / very_high / high / medium): ").strip().lower()
            if quality in ["ultra", "very_high", "high", "medium"]:
                config["quality"] = quality
                config["preset"] = "custom"
                save_config(config)
                if is_service_active():
                    subprocess.run(["systemctl", "--user", "restart", SERVICE_NAME], check=False)
        elif choice == "5":
            if HAS_RICH and console:
                codec = Prompt.ask("Codec seçin", choices=["hevc", "av1", "h264"], default=config.get("codec", "hevc"))
            else:
                codec = input("Codec (hevc / av1 / h264): ").strip().lower()
            if codec in ["hevc", "av1", "h264"]:
                config["codec"] = codec
                config["preset"] = "custom"
                save_config(config)
                if is_service_active():
                    subprocess.run(["systemctl", "--user", "restart", SERVICE_NAME], check=False)
        elif choice == "6":
            mins = input("Segment süresi (dakika cinsinden, örn: 30): ").strip()
            if mins.isdigit() and int(mins) > 0:
                config["max_duration_sec"] = int(mins) * 60
                save_config(config)
        elif choice == "7":
            recs = input("Maksimum tutulacak video sayısı (örn: 5): ").strip()
            if recs.isdigit() and int(recs) > 0:
                config["max_recordings"] = int(recs)
                save_config(config)
        elif choice == "8":
            config["record_mic"] = not config.get("record_mic", True)
            save_config(config)
            if is_service_active():
                subprocess.run(["systemctl", "--user", "restart", SERVICE_NAME], check=False)
        elif choice == "9":
            config["notifications"] = not config.get("notifications", True)
            save_config(config)
        elif choice == "10":
            break
def interactive_videos():
    while True:
        if HAS_RICH and console:
            console.clear()
        else:
            print('\033c', end='')
            
        recs = cmd_list()
        if not recs:
            input("\nGeri dönmek için Enter'a basın...")
            break
            
        print_msg("\nİşlemler: Oynatmak için numara girin | Silmek için 'd <no>' | Klasörü açmak için 'o' | Çıkış için 'q'", style="dim")
        try:
            choice = input("\nSeçim: ").strip().lower()
        except KeyboardInterrupt:
            return
            
        if choice == 'q':
            break
        elif choice == 'o':
            cmd_open()
        elif choice.startswith('d '):
            idx = choice.split(' ')[1]
            if idx.isdigit():
                cmd_delete(argparse.Namespace(index=int(idx)))
                time.sleep(0.5)
        elif choice.isdigit():
            cmd_play(argparse.Namespace(index=int(choice)))
            time.sleep(0.5)

def interactive_menu():
    while True:
        if HAS_RICH and console:
            console.clear()
        else:
            print('\033c', end='')

        is_rec = is_recording_active()
        is_svc = is_service_active()
        is_en = is_service_enabled()
        count, size_str, _ = get_storage_stats()
        cfg = load_config()

        if HAS_RICH and console:
            rec_text = "[bold green]● KAYIT ALINIYOR[/bold green]" if is_rec else "[bold red]○ BOŞTA (Kayıt Yok)[/bold red]"
            svc_text = "[green]Açık (Her açılışta oto-kayıt)[/green]" if is_en else "[dim]Kapalı[/dim]"
            
            preset_key = cfg.get("preset", "custom")
            p_name = PRESETS.get(preset_key, {}).get("name", "Özel")
            res_str = cfg.get("resolution", "native")
            res_resolved = resolve_resolution(res_str)
            res_display = res_resolved or "Native"
            
            content = f"Kayıt Durumu    : {rec_text}\n" \
                      f"Arka Plan Servis: {svc_text}\n" \
                      f"Aktif Profil    : [yellow]{p_name}[/yellow] ({res_display} @ {cfg.get('fps', 60)} FPS)\n" \
                      f"Donanım & Codec : [magenta]{cfg.get('codec', 'hevc').upper()}[/magenta] ({cfg.get('quality', 'very_high')})\n" \
                      f"Disk Durumu     : {count} / {cfg.get('max_recordings', 5)} video ({size_str})"
            console.print(Panel(content, title="🎥 Recorder CLI Dashboard", border_style="cyan", expand=False))
            
            options_table = Table(show_header=False, box=None)
            options_table.add_column("No", style="bold cyan", width=4)
            options_table.add_column("Açıklama", style="bold")
            
            options_table.add_row("1", "Kaydı Durdur" if is_rec else "Kaydı Başlat")
            options_table.add_row("2", "Arka Plan Otomatik Kayıt Servisini Aç/Kapat")
            options_table.add_row("3", "Videoları Yönet (Oynat, Sil, Klasörü Aç)")
            options_table.add_row("4", "Ayarlar (Profil, Çözünürlük, FPS, Kalite)")
            options_table.add_row("5", "Çıkış")
            console.print(options_table)
            
            try:
                choice = Prompt.ask("\nSeçiminiz", choices=["1", "2", "3", "4", "5"], default="5")
            except KeyboardInterrupt:
                print_msg("\nGörüşmek üzere!", style="cyan")
                break
        else:
            print("=== 🎥 Recorder CLI ===")
            print(f"Kayıt: {'🟢 AKTİF' if is_rec else '🔴 BOŞTA'}")
            print(f"Servis: {'🟢 Açık' if is_en else '⚪ Kapalı'}")
            print(f"Videolar: {count} adet ({size_str})")
            print("-" * 40)
            print("1. " + ("Kaydı Durdur" if is_rec else "Kaydı Başlat"))
            print("2. Arka Plan Servisini Aç/Kapat")
            print("3. Videoları Yönet")
            print("4. Ayarlar")
            print("5. Çıkış")
            try:
                choice = input("\nSeçim: ").strip()
            except KeyboardInterrupt:
                print("\nGörüşmek üzere!")
                break
            
        if choice == '1':
            if is_rec:
                cmd_stop()
            else:
                cmd_record()
            time.sleep(0.8)
        elif choice == '2':
            if is_en:
                cmd_service(argparse.Namespace(action="disable"))
            else:
                cmd_service(argparse.Namespace(action="enable"))
            time.sleep(1.0)
        elif choice == '3':
            interactive_videos()
        elif choice == '4':
            interactive_settings()
        elif choice == '5':
            print_msg("Görüşmek üzere!", style="cyan")
            break

def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    parser = argparse.ArgumentParser(
        description="Wayland için modern donanım hızlandırmalı döngüsel ekran kaydedici",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-v", "--version", action="version", version=f"recorder-cli {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Kullanılabilir komutlar")
    subparsers.required = True

    # record
    p_record = subparsers.add_parser("record", help="Ekran kaydını başlat")
    p_record.add_argument("--profile", "--preset", dest="preset", choices=list(PRESETS.keys()), help="Kayıt profili (performance, balanced, quality, ultra, esports)")
    p_record.add_argument("--res", dest="resolution", help="Geçici çözünürlük (1080p, 1440p, native, WxH)")
    p_record.add_argument("--fps", type=int, help="Geçici FPS (30, 60, 120)")
    p_record.add_argument("--quality", choices=["ultra", "very_high", "high", "medium"], help="Geçici kalite")
    p_record.add_argument("--codec", choices=["hevc", "av1", "h264"], help="Geçici video codec")
    p_record.set_defaults(func=cmd_record)

    # profile
    p_profile = subparsers.add_parser("profile", help="Kalite ve performans profilini seç veya listele")
    p_profile.add_argument("name", nargs="?", choices=list(PRESETS.keys()), help="Profil adı (performance, balanced, quality, ultra, esports)")
    p_profile.set_defaults(func=cmd_profile)

    # preset
    p_preset = subparsers.add_parser("preset", help="profile komutunun eşanlamlısı")
    p_preset.add_argument("name", nargs="?", choices=list(PRESETS.keys()), help="Profil adı (performance, balanced, quality, ultra, esports)")
    p_preset.set_defaults(func=cmd_profile)
    # stop
    p_stop = subparsers.add_parser("stop", help="Aktif kaydı durdur ve temizce kaydet")
    p_stop.set_defaults(func=cmd_stop)

    # status
    p_status = subparsers.add_parser("status", help="Kayıt, servis ve donanım durumunu göster")
    p_status.set_defaults(func=cmd_status)

    # list
    p_list = subparsers.add_parser("list", help="Kaydedilen videoları listele")
    p_list.set_defaults(func=cmd_list)

    # play
    p_play = subparsers.add_parser("play", help="Belirtilen kaydı oynat (örn: recorder play 1)")
    p_play.add_argument("index", type=int, nargs="?", default=1, help="Kayıt numarası (1 = en son)")
    p_play.set_defaults(func=cmd_play)

    # open
    p_open = subparsers.add_parser("open", help="Kayıt klasörünü dosya yöneticisinde aç")
    p_open.set_defaults(func=cmd_open)

    # delete
    p_delete = subparsers.add_parser("delete", help="Belirtilen kaydı sil")
    p_delete.add_argument("index", type=int, help="Silinecek kayıt numarası")
    p_delete.set_defaults(func=cmd_delete)

    # clean
    p_clean = subparsers.add_parser("clean", help="Tüm kayıtları sil")
    p_clean.set_defaults(func=cmd_clean)

    # service
    p_service = subparsers.add_parser("service", help="Systemd user servisini yönet")
    p_service.add_argument("action", choices=["enable", "disable", "start", "stop", "status", "install"], help="Servis eylemi")
    p_service.set_defaults(func=cmd_service)

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Döngüsel kayıt motorunu ön planda çalıştır (systemd için)")
    p_daemon.set_defaults(func=cmd_daemon)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
