"""Test audio device configuration."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.sync.sync_recorder import SyncRecorder, RecordingConfig
from config.settings import settings

print("=== 現在のオーディオ設定 ===")
print(f"デバイス名: {settings.audio.device_name}")
print(f"チャンネル数: {settings.audio.channels}")
print(f"サンプルレート: {settings.audio.sample_rate}")
print()

print("=== 利用可能な入力デバイス ===")
devices = SyncRecorder.list_audio_devices()
for d in devices:
    marker = " <-- 候補" if settings.audio.device_name and settings.audio.device_name.lower() in d["name"].lower() else ""
    print(f"  {d['index']}: {d['name']} ({d['channels']}ch){marker}")
print()

print("=== デバイス解決テスト ===")
config = RecordingConfig(
    device=settings.audio.device_name,
    channels=settings.audio.channels,
    sample_rate=settings.audio.sample_rate,
)
recorder = SyncRecorder(output_dir=Path("data/recordings"), config=config)
resolved_id = recorder._resolve_device_id(settings.audio.device_name)
print(f"  設定デバイス名: {settings.audio.device_name}")
print(f"  解決されたID: {resolved_id}")
if resolved_id is not None:
    import sounddevice as sd
    dev = sd.query_devices(resolved_id)
    print(f"  実際のデバイス: {dev['name']}")
    print(f"  入力チャンネル数: {dev['max_input_channels']}")
print()

print("=== デフォルト入力デバイス ===")
default = SyncRecorder.get_default_device()
if default:
    print(f"  {default['index']}: {default['name']} ({default['channels']}ch)")
else:
    print("  (不明)")

