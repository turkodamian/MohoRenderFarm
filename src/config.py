"""Application configuration management."""
import json
import os
from pathlib import Path

APP_NAME = "Moho Render Farm"
APP_VERSION = "1.4.5"
APP_AUTHOR = "Damián Turkieh"

DEFAULT_MOHO_PATH = r"C:\Program Files\Moho 14\Moho.exe"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "MohoRenderFarm"
CONFIG_FILE = CONFIG_DIR / "config.json"
QUEUE_DIR = CONFIG_DIR / "queues"
PRESETS_DIR = CONFIG_DIR / "presets"
AUTOSAVE_QUEUE_FILE = CONFIG_DIR / "autosave_queue.json"

DEFAULT_CONFIG = {
    "moho_path": DEFAULT_MOHO_PATH,
    "default_output_dir": "",
    "default_output_mode": "project",
    "default_format": "MP4",
    "default_options": "MP4 (MPEG4-AAC)",
    "default_multithread": True,
    "default_verbose": True,
    "network_port": 5580,
    "network_master_host": "localhost",
    "recent_projects": [],
    "recent_queues": [],
    "max_recent": 20,
    "default_preset": "",
    "auto_send_to_farm": False,
    "max_local_renders": 1,
    "auto_check_updates": True,
}

FORMATS = [
    "JPEG",
    "TGA",
    "BMP",
    "PNG",
    "PSD",
    "QT",
    "MP4",
    "Animated GIF",
]

FORMAT_PRESETS = {
    "MP4": [
        "MP4 (MPEG4-AAC)",
        "MP4 (H.265-AAC)",
    ],
    "QT": [
        "MOV (ProRes alpha-ALAC)",
        "MOV (PNG alpha-PCM)",
        "MOV (MJPEG-AAC)",
        "MOV (MPEG4-AAC)",
    ],
}

# Windows-only video presets
WINDOWS_PRESETS = {
    "MP4": [
        "MP4 (MPEG4-AAC)",
        "MP4 (H.265-AAC)",
    ],
    "QT": [
        "MOV (ProRes alpha-ALAC)",
        "MOV (PNG alpha-PCM)",
        "MOV (MJPEG-AAC)",
        "MOV (MPEG4-AAC)",
    ],
    "M4V": [
        "M4V (MPEG4-AAC)",
    ],
    "AVI": [
        "AVI (PNG alpha-PCM)",
        "AVI (MJPEG-PCM)",
        "AVI (Raw-PCM)",
    ],
    "ASF": [
        "ASF (WMV-WMA)",
        "ASF (Raw-PCM)",
        "ASF (PNG alpha-PCM)",
        "ASF (MJPEG-PCM)",
    ],
}

RESOLUTIONS = {
    "Project Default": None,
    "4K UHD (3840x2160)": (3840, 2160),
    "2K QHD (2560x1440)": (2560, 1440),
    "Full HD 1080p (1920x1080)": (1920, 1080),
    "HD 720p (1280x720)": (1280, 720),
    "SD 480p (854x480)": (854, 480),
    "SD 360p (640x360)": (640, 360),
}

MOHO_FILE_EXTENSIONS = [".moho", ".anime", ".anme"]

# Bug report Discord webhook
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1471430444892426280/dLk-_95ylUmIFWqW4Zy4WXtjkD6hSt5xwqh_htK_W3IqbCJUeMKzsomCmfn44I8FdB1E"

QUALITY_LEVELS = {
    0: "Minimum",
    1: "Low",
    2: "Normal",
    3: "High",
    4: "Max",
    5: "Lossless",
}


class AppConfig:
    """Manages application configuration with persistence."""

    def __init__(self):
        self._config = dict(DEFAULT_CONFIG)
        self._ensure_dirs()
        self.load()

    def _ensure_dirs(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for key in DEFAULT_CONFIG:
                    if key in saved:
                        self._config[key] = saved[key]
            except (json.JSONDecodeError, IOError):
                pass

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def add_recent_project(self, path):
        recents = self._config.get("recent_projects", [])
        path = str(path)
        if path in recents:
            recents.remove(path)
        recents.insert(0, path)
        self._config["recent_projects"] = recents[: self._config["max_recent"]]
        self.save()

    def add_recent_queue(self, path):
        recents = self._config.get("recent_queues", [])
        path = str(path)
        if path in recents:
            recents.remove(path)
        recents.insert(0, path)
        self._config["recent_queues"] = recents[: self._config["max_recent"]]
        self.save()

    @property
    def moho_path(self):
        return self._config["moho_path"]

    @moho_path.setter
    def moho_path(self, value):
        self.set("moho_path", value)
