import os
import sys
import json
import shutil
import ctypes
import time
import traceback
from ctypes import wintypes

from PyQt6.QtCore import (
    Qt, QUrl, QRect, QRectF, QTimer, QSize, pyqtSignal, QPoint, QObject,
    QAbstractNativeEventFilter, QEvent
)
from PyQt6.QtGui import (
    QPainter, QPainterPath, QPixmap, QColor, QPen, QFont,
    QLinearGradient, QBrush, QIcon, QAction
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDialog,
    QFileDialog, QListWidgetItem, QSizePolicy, QSlider, QPushButton,
    QComboBox, QScrollArea, QFrame, QStackedWidget, QSystemTrayIcon,
    QMenu, QListWidget, QColorDialog
)
from PyQt6.QtMultimedia import QMediaPlayer, QVideoSink, QAudioOutput

from qfluentwidgets import (
    PrimaryPushButton, BodyLabel, TitleLabel, SubtitleLabel, StrongBodyLabel,
    CaptionLabel, SwitchButton, ListWidget, setTheme, Theme,
    FluentIcon as FIF, InfoBar, ToolButton, ComboBox as FluentComboBox,
    PushButton, SpinBox, Slider, CardWidget,
    FluentWindow, NavigationItemPosition, MessageBox,
    qconfig,
)


# ═══════════════════════════════════════════════════════════════════════════
# Win32 常量
# ═══════════════════════════════════════════════════════════════════════════
HWND_BOTTOM = 1
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_FLAGS = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_BORDER_COLOR = 34
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
DWMWCP_ROUND = 2
DWMWCP_DONOTROUND = 1
DWMWA_COLOR_NONE = 0xFFFFFFFE

SW_MINIMIZE = 6
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

MIN_WIN_WIDTH = 300
MIN_WIN_HEIGHT = 200

BORDER_NONE = 0
BORDER_GLASS = 1
BORDER_SOLID = 2
BORDER_LABELS = ["无边框", "Win11毛玻璃", "纯色边框"]
BORDER_DEFAULT_WIDTH = {BORDER_NONE: 0, BORDER_GLASS: 10, BORDER_SOLID: 4}
DEFAULT_BORDER_COLOR = "#000000"

AUTOSTART_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_APP_NAME = "DeskVideo"
AUTOSTART_FLAG = "--autostart"

DEFAULT_FPS_LIMIT = 30
DEFAULT_RENDER_QUALITY = "high"
DEFAULT_OCCLUSION_STOP_PERCENT = 100
DEFAULT_OCCLUSION_KEEP_AUDIO = True


# ═══════════════════════════════════════════════════════════════════════════
# 系统主题检测
# ═══════════════════════════════════════════════════════════════════════════
def get_system_theme() -> str:
    """读取 Windows 系统应用主题，返回 'light' 或 'dark'。"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0, winreg.KEY_READ,
        )
        try:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if value else "dark"
        finally:
            winreg.CloseKey(key)
    except Exception:
        return "light"


def set_title_bar_dark(hwnd: int, dark: bool):
    """设置 Windows 原生标题栏为深色/浅色。对无边框窗口无效。"""
    try:
        value = ctypes.c_int(1 if dark else 0)
        # Win10 1903+ 用 20，旧版本用 19
        for attr in (DWMWA_USE_IMMERSIVE_DARK_MODE,
                     DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value),
                )
                return
            except Exception:
                continue
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# 主题系统 —— 单一数据源，支持 auto/light/dark 三态
# ═══════════════════════════════════════════════════════════════════════════
class ThemeManager:
    """全局主题管理器。

    - mode: 'auto' | 'light' | 'dark'
    - 实际生效颜色由 _resolved ('light' | 'dark') 决定
    - auto 时通过 get_system_theme() 读取系统主题
    """

    # ── 明色主题 ────────────────────────────────────────────────────────
    LIGHT = {
        "window_bg":         "#F6F7F9",
        "window_bg_alt":     "#FFFFFF",
        "page_bg":           "#F6F7F9",
        "nav_bg":            "#F3F5F7",
        "card_bg":           "#FFFFFF",
        "card_bg_alt":       "#F1F3F5",
        "card_hover":        "#F7F8FA",
        "card_border":       "#E4E7EC",
        "border":            "#D9DDE3",
        "border_strong":     "#C7CDD6",
        "separator":         "#EAECF0",
        "text":              "#1F2329",
        "text_secondary":    "#667085",
        "text_tertiary":     "#98A2B3",
        "text_on_accent":    "#FFFFFF",
        "text_link":         "#2563EB",
        "accent":            "#2563EB",
        "accent_hover":      "#1D4ED8",
        "accent_pressed":    "#1E40AF",
        "accent_subtle":     "#EAF2FF",
        "accent_light":      "#93C5FD",
        "button_bg":         "#FFFFFF",
        "button_bg_hover":   "#F2F4F7",
        "button_bg_pressed": "#E9EDF2",
        "button_border":     "#CDD3DC",
        "input_bg":          "#FFFFFF",
        "input_border":      "#CDD3DC",
        "input_focus":       "#2563EB",
        "input_text":        "#1F2329",
        "input_placeholder": "#98A2B3",
        "video_bg":          "#000000",
        "video_placeholder": "#93C5FD",
        "glass_top":         "#FFFFFF",
        "glass_bottom":      "#E7EAF0",
        "scrollbar":         "#CDD3DC",
        "list_selected":     "#EAF2FF",
        "panel_bg":          "#FFFFFF",
        "panel_border":      "#D9DDE3",
    }

    # ── 暗色主题 ────────────────────────────────────────────────────────
    DARK = {
        "window_bg":         "#1A1D21",
        "window_bg_alt":     "#202328",
        "page_bg":           "#1A1D21",
        "nav_bg":            "#202328",
        "card_bg":           "#23262B",
        "card_bg_alt":       "#2A2D33",
        "card_hover":        "#2E3238",
        "card_border":       "#33373D",
        "border":            "#3A3E45",
        "border_strong":     "#4A4F57",
        "separator":         "#33373D",
        "text":              "#E8EAED",
        "text_secondary":    "#A0A6B0",
        "text_tertiary":     "#6B7280",
        "text_on_accent":    "#FFFFFF",
        "text_link":         "#60A5FA",
        "accent":            "#60A5FA",
        "accent_hover":      "#3B82F6",
        "accent_pressed":    "#2563EB",
        "accent_subtle":     "#1E3A5F",
        "accent_light":      "#3B82F6",
        "button_bg":         "#2A2D33",
        "button_bg_hover":   "#33373D",
        "button_bg_pressed": "#3A3E45",
        "button_border":     "#4A4F57",
        "input_bg":          "#2A2D33",
        "input_border":      "#4A4F57",
        "input_focus":       "#60A5FA",
        "input_text":        "#E8EAED",
        "input_placeholder": "#6B7280",
        "video_bg":          "#000000",
        "video_placeholder": "#3B82F6",
        "glass_top":         "#2A2D33",
        "glass_bottom":      "#1A1D21",
        "scrollbar":         "#4A4F57",
        "list_selected":     "#1E3A5F",
        "panel_bg":          "#23262B",
        "panel_border":      "#3A3E45",
    }

    def __init__(self):
        self._mode = "auto"       # 用户选择：auto / light / dark
        self._resolved = "light"  # 当前实际生效：light / dark
        self._ready = False       # QApplication 是否已就绪

    @property
    def mode(self) -> str:
        return self._mode

    def is_dark(self) -> bool:
        return self._resolved == "dark"

    def color(self, key: str, fallback: str = "#000000") -> str:
        palette = self.DARK if self._resolved == "dark" else self.LIGHT
        return palette.get(key, fallback)

    def qcolor(self, key: str, fallback: str = "#000000") -> QColor:
        return QColor(self.color(key, fallback))

    def set_mode(self, mode: str, force: bool = False):
        """设置主题模式并立即应用。mode ∈ {'auto','light','dark'}。"""
        if mode not in ("auto", "light", "dark"):
            mode = "auto"
        changed = (mode != self._mode) or force
        self._mode = mode
        resolved = get_system_theme() if mode == "auto" else mode
        resolved_changed = (resolved != self._resolved) or force
        self._resolved = resolved
        if changed or resolved_changed:
            self._apply()

    def refresh_auto(self):
        """auto 模式下重新读取系统主题；非 auto 模式无操作。"""
        if self._mode != "auto":
            return
        resolved = get_system_theme()
        if resolved != self._resolved:
            self._resolved = resolved
            self._apply()

    def _apply(self):
        """把主题推送给 qfluentwidgets 和所有订阅者。"""
        if not self._ready:
            return
        try:
            setTheme(Theme.LIGHT if self._resolved == "light" else Theme.DARK,
                     save=False)
        except Exception:
            pass
        try:
            THEME_NOTIFIER.changed.emit(self._resolved)
        except Exception:
            pass

    def mark_ready(self):
        """在 QApplication 创建后调用一次，之后 set_mode 才会真正生效。"""
        self._ready = True


class _ThemeNotifier(QObject):
    changed = pyqtSignal(str)


THEME = ThemeManager()
THEME_NOTIFIER = _ThemeNotifier()


def themed(widget_cls):
    """装饰器：自动订阅主题变化。"""
    original_init = widget_cls.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        try:
            THEME_NOTIFIER.changed.connect(self._handle_theme_change)
        except Exception:
            pass

    def _handle_theme_change(self, _mode=""):
        try:
            if hasattr(self, "_on_theme_changed"):
                self._on_theme_changed()
        except Exception:
            pass
        try:
            self.update()
        except Exception:
            pass

    widget_cls.__init__ = new_init
    widget_cls._handle_theme_change = _handle_theme_change
    return widget_cls


class SystemThemeWatcher(QObject):
    """定时检查系统主题，auto 模式下自动切换。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._check)
        self._timer.start()

    def _check(self):
        try:
            THEME.refresh_auto()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# 带主题背景的页面基类
# ═══════════════════════════════════════════════════════════════════════════
@themed
class ThemedPage(QWidget):
    """带主题背景色的页面。解决 home/settings 页在深/浅色下的底色不一致问题。"""
    def __init__(self, object_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply_bg()

    def _apply_bg(self):
        bg = THEME.color("page_bg")
        self.setStyleSheet(
            f"#{self.objectName()} {{ background-color: {bg}; }}"
        )

    def _on_theme_changed(self):
        self._apply_bg()


# ═══════════════════════════════════════════════════════════════════════════
# Win32 工具函数
# ═══════════════════════════════════════════════════════════════════════════
def set_win11_round_corner(hwnd: int, preference: int = DWMWCP_ROUND):
    try:
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(ctypes.c_int(preference)),
            ctypes.sizeof(ctypes.c_int),
        )
    except Exception:
        pass


def disable_dwm_border(hwnd: int):
    try:
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_BORDER_COLOR,
            ctypes.byref(ctypes.c_uint(DWMWA_COLOR_NONE)),
            ctypes.sizeof(ctypes.c_uint),
        )
    except Exception:
        pass


def disable_dwm_round_corner(hwnd: int):
    try:
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(ctypes.c_int(DWMWCP_DONOTROUND)),
            ctypes.sizeof(ctypes.c_int),
        )
    except Exception:
        pass


def set_tool_window(hwnd: int):
    try:
        user32 = ctypes.windll.user32
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex = (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
    except Exception:
        pass


def setup_frameless_window(hwnd: int):
    disable_dwm_round_corner(hwnd)
    disable_dwm_border(hwnd)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long), ("top", ctypes.c_long),
        ("right", ctypes.c_long), ("bottom", ctypes.c_long),
    ]


def minimize_other_windows(skip_hwnds) -> list:
    user32 = ctypes.windll.user32
    skip = set(skip_hwnds)
    result = []

    ENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
    )

    def _callback(hwnd, lParam):
        try:
            h = int(hwnd)
            if h in skip: return True
            if not user32.IsWindowVisible(hwnd): return True
            if user32.IsIconic(hwnd): return True
            if user32.GetWindowTextLengthW(hwnd) == 0: return True
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if ex & (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE): return True
            rect = RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)): return True
            w = rect.right - rect.left
            hh = rect.bottom - rect.top
            if w < MIN_WIN_WIDTH or hh < MIN_WIN_HEIGHT: return True
            user32.ShowWindow(hwnd, SW_MINIMIZE)
            result.append(h)
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(ENUMPROC(_callback), 0)
    except Exception:
        pass
    return result


def get_occlusion_ratio(hwnd: int) -> float:
    try:
        user32 = ctypes.windll.user32
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return 1.0

        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return 0.0

        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w <= 0 or h <= 0:
            return 1.0

        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)

        points = []
        cols = 8
        rows = 8
        for j in range(rows):
            yy = rect.top + (2 * j + 1) * h // (2 * rows)
            for i in range(cols):
                xx = rect.left + (2 * i + 1) * w // (2 * cols)
                points.append((xx, yy))

        edge_n = 8
        for i in range(edge_n):
            x = rect.left + i * max(0, w - 1) // max(1, edge_n - 1)
            points.append((x, rect.top))
            points.append((x, rect.bottom - 1))
            y = rect.top + i * max(0, h - 1) // max(1, edge_n - 1)
            points.append((rect.left, y))
            points.append((rect.right - 1, y))

        total = len(points)
        if total == 0:
            return 0.0

        occluded = 0
        for x, y in points:
            if x < 0 or y < 0 or x >= screen_w or y >= screen_h:
                continue
            pt = wintypes.POINT(x, y)
            top = user32.WindowFromPoint(pt)
            if not top:
                occluded += 1
                continue
            root = user32.GetAncestor(top, 2)
            if root != hwnd and top != hwnd:
                occluded += 1

        return occluded / total
    except Exception:
        return 0.0


def is_window_fully_occluded(hwnd: int) -> bool:
    return get_occlusion_ratio(hwnd) >= 0.995


def _get_launch_command() -> str:
    if "__compiled__" in globals():
        exe = os.path.abspath(sys.argv[0])
        return f'"{exe}" {AUTOSTART_FLAG}'
    if getattr(sys, 'frozen', False):
        exe = os.path.abspath(sys.executable)
        return f'"{exe}" {AUTOSTART_FLAG}'
    python_exe = os.path.abspath(sys.executable)
    script = os.path.abspath(__file__)
    return f'"{python_exe}" "{script}" {AUTOSTART_FLAG}'


def is_autostart_enabled() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH, 0, winreg.KEY_READ
        )
        try:
            winreg.QueryValueEx(key, AUTOSTART_APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def set_autostart_enabled(enabled: bool) -> tuple:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        try:
            if enabled:
                winreg.SetValueEx(key, AUTOSTART_APP_NAME, 0,
                                  winreg.REG_SZ, _get_launch_command())
            else:
                try:
                    winreg.DeleteValue(key, AUTOSTART_APP_NAME)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
        return True, ""
    except Exception as e:
        return False, str(e)


def ensure_autostart_command_current():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, AUTOSTART_REG_PATH, 0, winreg.KEY_READ
        )
        try:
            current, _ = winreg.QueryValueEx(key, AUTOSTART_APP_NAME)
        except FileNotFoundError:
            return
        finally:
            winreg.CloseKey(key)
        if current != _get_launch_command():
            set_autostart_enabled(True)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# 快捷键
# ═══════════════════════════════════════════════════════════════════════════
_KEY_ALIASES = {
    'CTRL': MOD_CONTROL, 'CONTROL': MOD_CONTROL,
    'ALT': MOD_ALT, 'SHIFT': MOD_SHIFT, 'WIN': MOD_WIN, 'META': MOD_WIN,
}

_VK_MAP = {}
for _c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    _VK_MAP[_c] = ord(_c)
for _d in '0123456789':
    _VK_MAP[_d] = ord(_d)
for _i in range(1, 25):
    _VK_MAP[f'F{_i}'] = 0x70 + (_i - 1)
_VK_MAP.update({
    'SPACE': 0x20, 'ESC': 0x1B, 'ESCAPE': 0x1B, 'TAB': 0x09,
    'ENTER': 0x0D, 'RETURN': 0x0D, 'BACKSPACE': 0x08,
    'DELETE': 0x2E, 'DEL': 0x2E, 'INSERT': 0x2D,
    'HOME': 0x24, 'END': 0x23, 'PAGEUP': 0x21, 'PAGEDOWN': 0x22,
    'UP': 0x26, 'DOWN': 0x28, 'LEFT': 0x25, 'RIGHT': 0x27,
    'PLUS': 0x6B, 'MINUS': 0x6D, 'COMMA': 0xBC, 'PERIOD': 0xBE,
    'SLASH': 0xBF, 'SEMICOLON': 0xBA, 'QUOTE': 0xDE,
    'BRACKETLEFT': 0xDB, 'BRACKETRIGHT': 0xDD, 'BACKSLASH': 0xDC,
})


def parse_hotkey(s: str):
    if not s:
        return None, None
    parts = [p.strip().upper() for p in s.split('+') if p.strip()]
    if not parts:
        return None, None
    mods = 0
    vk = None
    for p in parts:
        if p in _KEY_ALIASES:
            mods |= _KEY_ALIASES[p]
        elif p in _VK_MAP:
            vk = _VK_MAP[p]
        else:
            return None, None
    if vk is None or mods == 0:
        return None, None
    return mods, vk


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback, hotkey_id: int = 0xB001):
        super().__init__()
        self._callback = callback
        self._hotkey_id = hotkey_id
        self._registered = False

    def register(self, hotkey_str: str) -> bool:
        self.unregister()
        mods, vk = parse_hotkey(hotkey_str)
        if mods is None:
            return False
        try:
            ok = ctypes.windll.user32.RegisterHotKey(
                None, self._hotkey_id, mods | MOD_NOREPEAT, vk
            )
            self._registered = bool(ok)
            return self._registered
        except Exception as e:
            print(f"[热键注册失败] {e}")
            return False

    def unregister(self):
        if self._registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self._hotkey_id)
            except Exception:
                pass
            self._registered = False

    def nativeEventFilter(self, eventType, message):
        try:
            if bytes(eventType) == b"windows_generic_MSG":
                msg = ctypes.cast(
                    int(message), ctypes.POINTER(wintypes.MSG)
                ).contents
                if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                    try:
                        self._callback()
                    except Exception:
                        pass
        except Exception:
            pass
        return False, 0


# ═══════════════════════════════════════════════════════════════════════════
# 路径 / 设置
# ═══════════════════════════════════════════════════════════════════════════
def get_app_dir() -> str:
    if "__compiled__" in globals():
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir() -> str:
    d = os.path.join(get_app_dir(), 'data')
    os.makedirs(d, exist_ok=True)
    return d


def get_video_dir() -> str:
    d = os.path.join(get_app_dir(), 'video')
    os.makedirs(d, exist_ok=True)
    return d


VIDEO_EXTS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v')
APP_SETTINGS_FILE = 'app_settings.json'


class AppSettings:
    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, APP_SETTINGS_FILE)
        self.data = {
            "hotkey": "Ctrl+Alt+Q",
            "initialized": False,
            "minimize_to_tray": True,
            "auto_start": False,
            "auto_run_enabled": False,
            "auto_run_configs": [],
            "fps_limit": DEFAULT_FPS_LIMIT,
            "render_quality": DEFAULT_RENDER_QUALITY,
            "occlusion_stop_percent": DEFAULT_OCCLUSION_STOP_PERCENT,
            "occlusion_keep_audio": DEFAULT_OCCLUSION_KEEP_AUDIO,
            "theme_mode": "auto",   # 默认跟随系统
        }
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    self.data.update(d)
            except Exception as e:
                print(f"[设置加载失败] {e}")

    def save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[设置保存失败] {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()


def default_config(video: str = "", loop: bool = True) -> dict:
    return {
        "video": video, "loop": loop,
        "x": 120, "y": 120, "width": 900, "height": 540,
        "radius": 12, "volume": 0.8, "opacity": 1.0,
        "draggable": True, "layer": 0,
        "border": BORDER_NONE, "border_width": 10,
        "border_color": DEFAULT_BORDER_COLOR,
    }


class ConfigManager:
    def __init__(self, data_dir: str):
        self.dir = data_dir
        self._data: dict[str, dict] = {}
        self.load()

    def _path(self, name: str) -> str:
        return os.path.join(self.dir, f"{name}.json")

    def load(self):
        self._data = {}
        if not os.path.isdir(self.dir):
            return
        for fname in os.listdir(self.dir):
            if not fname.lower().endswith('.json'):
                continue
            if fname == APP_SETTINGS_FILE:
                continue
            name = fname[:-5]
            try:
                with open(os.path.join(self.dir, fname), 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                if isinstance(cfg, dict):
                    self._data[name] = cfg
            except Exception as e:
                print(f"[配置加载失败] {fname}: {e}")

    def all(self):
        return self._data

    def get(self, name):
        return self._data.get(name)

    def set(self, name, cfg) -> tuple:
        self._data[name] = dict(cfg)
        path = self._path(name)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            if not os.path.exists(path):
                return False, f"文件未创建：{path}"
            return True, path
        except Exception as e:
            return False, str(e)

    def delete(self, name):
        if name in self._data:
            del self._data[name]
        p = self._path(name)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception as e:
                print(f"[配置删除失败] {name}: {e}")

    def has(self, name):
        return name in self._data


# ═══════════════════════════════════════════════════════════════════════════
# 绘制辅助
# ═══════════════════════════════════════════════════════════════════════════
def _rounded(rect: QRectF, r: float) -> QPainterPath:
    path = QPainterPath()
    r = max(0.0, min(r, rect.width() / 2, rect.height() / 2))
    path.addRoundedRect(rect, r, r)
    return path


def draw_outer_bg(painter, rect, radius, border_type, bw, border_color=None):
    if border_type == BORDER_GLASS and bw > 0:
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        top = THEME.qcolor("glass_top"); top.setAlpha(95)
        bottom = THEME.qcolor("glass_bottom"); bottom.setAlpha(70)
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bottom)
        painter.fillRect(rect, QBrush(grad))
    elif border_type == BORDER_SOLID and bw > 0:
        c = QColor(border_color) if border_color else QColor(DEFAULT_BORDER_COLOR)
        if not c.isValid():
            c = QColor(DEFAULT_BORDER_COLOR)
        painter.fillRect(rect, c)
    else:
        painter.fillRect(rect, THEME.qcolor("card_bg"))


def draw_border_ornament(painter, outer, inner, outer_r, inner_r, btype, bw):
    if btype == BORDER_GLASS and bw > 0:
        p = QPen(THEME.qcolor("glass_top"), 1.4)
        p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(p)
        painter.drawPath(_rounded(inner, inner_r))
        c2 = THEME.qcolor("glass_top"); c2.setAlpha(90)
        p = QPen(c2, 1)
        painter.setPen(p)
        painter.drawPath(_rounded(outer.adjusted(0.5, 0.5, -0.5, -0.5), outer_r))


# ═══════════════════════════════════════════════════════════════════════════
# 视频画布
# ═══════════════════════════════════════════════════════════════════════════
@themed
class VideoCanvas(QWidget):
    def __init__(self, radius=12, border_type=BORDER_NONE,
                 border_width_px=10, border_color=DEFAULT_BORDER_COLOR,
                 parent=None):
        super().__init__(parent)
        self.radius = radius
        self.border_type = border_type
        self.border_width_px = border_width_px
        self.border_color = border_color
        self._pixmap = None
        self._cached = None
        self._cached_size = None
        self._cached_quality = None
        self._quality = "high"
        self._frame_update_pending = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._drag_start = None
        self._window_start = None

    def set_radius(self, r):
        self.radius = int(r); self.update()

    def set_border(self, t, w, color=None):
        self.border_type = int(t)
        self.border_width_px = int(w)
        if color is not None:
            self.border_color = color
        self.update()

    def set_render_quality(self, quality: str):
        if quality not in ("high", "balanced", "performance"):
            quality = "high"
        if quality != self._quality:
            self._quality = quality
            self._cached = None
            self._cached_size = None
            self._cached_quality = None
            self.update()

    def set_frame(self, image):
        if image is None or image.isNull():
            return
        self._pixmap = QPixmap.fromImage(image)
        self._cached = None
        if not self._frame_update_pending:
            self._frame_update_pending = True
            self.update()

    def clear_frames(self):
        self._pixmap = None
        self._cached = None
        self._cached_size = None
        self._cached_quality = None
        self.update()

    def _effective_bw(self):
        if self.border_type == BORDER_NONE:
            return 0
        return max(0, self.border_width_px)

    def paintEvent(self, event):
        self._frame_update_pending = False
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform,
            self._quality != "performance",
        )
        W, H = self.width(), self.height()
        outer = QRectF(0, 0, W, H)
        bw = self._effective_bw()
        r = max(0.0, min(float(self.radius), W / 2, H / 2))

        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(0, 0, W, H, Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        p.setClipPath(_rounded(outer, r))
        draw_outer_bg(p, outer, r, self.border_type, bw, self.border_color)

        inner = outer.adjusted(bw, bw, -bw, -bw) if bw > 0 else outer
        ir = max(0.0, r - bw) if bw > 0 else r

        p.save()
        p.setClipPath(_rounded(inner, ir), Qt.ClipOperation.ReplaceClip)
        p.fillRect(inner, THEME.qcolor("video_bg"))
        if self._pixmap is not None and not self._pixmap.isNull():
            target = inner.size().toSize()
            if target.width() > 0 and target.height() > 0:
                if (self._cached is None
                        or self._cached_size != target
                        or self._cached_quality != self._quality):
                    mode = (Qt.TransformationMode.FastTransformation
                            if self._quality == "performance"
                            else Qt.TransformationMode.SmoothTransformation)
                    self._cached = self._pixmap.scaled(
                        target,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        mode,
                    )
                    self._cached_size = target
                    self._cached_quality = self._quality
                if self._cached.width() > 0 and self._cached.height() > 0:
                    x = inner.x() + (inner.width() - self._cached.width()) / 2
                    y = inner.y() + (inner.height() - self._cached.height()) / 2
                    p.drawPixmap(int(x), int(y), self._cached)
        p.restore()

        if bw > 0:
            draw_border_ornament(p, outer, inner, r, ir,
                                 self.border_type, bw)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            win = self.window()
            if not getattr(win, 'is_draggable', lambda: True)():
                return
            self._drag_start = e.globalPosition().toPoint()
            self._window_start = win.pos()
            e.accept(); return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_start is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            delta = e.globalPosition().toPoint() - self._drag_start
            self.window().move(self._window_start + delta)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_start = None


# ═══════════════════════════════════════════════════════════════════════════
# 视频窗口
# ═══════════════════════════════════════════════════════════════════════════
class VideoWindow(QWidget):
    closed = pyqtSignal(object)
    LAYER_DESKTOP = 0
    LAYER_NORMAL = 1
    LAYER_TOP = 2

    def __init__(self, title, video_path, config, parent=None):
        super().__init__(parent)
        self.config_name = title
        self.video_path = video_path
        self.video_name = os.path.basename(video_path)
        self.config = dict(config)
        self.from_config = True

        self._layer = int(config.get('layer', self.LAYER_DESKTOP))
        self._locked = False
        self._loop = bool(config.get('loop', True))
        self._draggable = bool(config.get('draggable', True))
        self.radius = int(config.get('radius', 12))
        self.border_type = int(config.get('border', BORDER_NONE))
        self.border_width_px = int(config.get(
            'border_width', BORDER_DEFAULT_WIDTH.get(self.border_type, 10)
        ))
        self.border_color = config.get('border_color', DEFAULT_BORDER_COLOR)
        self._dragging = False

        self._occluded = False
        self._fps_limit = DEFAULT_FPS_LIMIT
        self._min_frame_interval = (
            1.0 / self._fps_limit if self._fps_limit > 0 else 0.0
        )
        self._last_frame_t = 0.0
        self._quality = DEFAULT_RENDER_QUALITY
        self._occlusion_stop_percent = DEFAULT_OCCLUSION_STOP_PERCENT
        self._keep_audio_when_occluded = DEFAULT_OCCLUSION_KEEP_AUDIO

        self._has_audio = True
        self._released = False
        self._saved_position = 0

        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMinimumSize(200, 120)

        x = int(config.get('x', 120)); y = int(config.get('y', 120))
        w = max(200, int(config.get('width', 900)))
        h = max(120, int(config.get('height', 540)))
        self.setGeometry(x, y, w, h)
        self.setWindowOpacity(max(0.1, min(1.0, float(config.get('opacity', 1.0)))))
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(float(config.get('volume', 0.8)))

        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.sink = QVideoSink(self)
        self.player.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._on_frame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = VideoCanvas(self.radius, self.border_type,
                                   self.border_width_px, self.border_color, self)
        self.canvas.set_render_quality(self._quality)
        layout.addWidget(self.canvas)

        self.player.setSource(QUrl.fromLocalFile(video_path))
        self.player.setLoops(
            QMediaPlayer.Loops.Infinite if self._loop else QMediaPlayer.Loops.Once
        )
        self.player.mediaStatusChanged.connect(self._on_media_status)

        self._bottom_timer = QTimer(self)
        self._bottom_timer.setInterval(500)
        self._bottom_timer.timeout.connect(self._send_to_bottom)

        self._occlusion_timer = QTimer(self)
        self._occlusion_timer.setInterval(1000)
        self._occlusion_timer.timeout.connect(self._check_occlusion)
        self._occlusion_timer.start()

        QTimer.singleShot(0, self._apply_win32_styles)
        QTimer.singleShot(0, lambda: self.set_layer(self._layer, force=True))

        self.player.play()

    def _apply_win32_styles(self):
        hwnd = int(self.winId())
        setup_frameless_window(hwnd)
        set_tool_window(hwnd)

    def is_draggable(self):
        return self._draggable and not self._locked

    def set_draggable(self, b):
        self._draggable = bool(b)

    def _set_z_order(self, insert_after):
        try:
            ctypes.windll.user32.SetWindowPos(
                int(self.winId()), insert_after, 0, 0, 0, 0, SWP_FLAGS
            )
        except Exception:
            pass

    def _send_to_bottom(self):
        self._set_z_order(HWND_BOTTOM)

    def set_layer(self, layer, force=False):
        if not force and layer == self._layer:
            return
        self._layer = layer
        if layer == self.LAYER_DESKTOP:
            self._set_z_order(HWND_BOTTOM)
            self._bottom_timer.start()
        elif layer == self.LAYER_TOP:
            self._bottom_timer.stop()
            self._set_z_order(HWND_TOPMOST)
        else:
            self._bottom_timer.stop()
            self._set_z_order(HWND_NOTOPMOST)

    def get_layer(self):
        return self._layer

    def set_locked(self, locked):
        self._locked = bool(locked)
        if self._locked and self._layer != self.LAYER_TOP:
            self.set_layer(self.LAYER_TOP)

    def is_locked(self):
        return self._locked

    def set_loop(self, loop):
        self._loop = bool(loop)
        self.player.setLoops(
            QMediaPlayer.Loops.Infinite if self._loop else QMediaPlayer.Loops.Once
        )

    def get_loop(self):
        return self._loop

    def set_playback_options(
        self,
        fps_limit: int = DEFAULT_FPS_LIMIT,
        quality: str = DEFAULT_RENDER_QUALITY,
        occlusion_stop_percent: int = DEFAULT_OCCLUSION_STOP_PERCENT,
        occlusion_keep_audio: bool = DEFAULT_OCCLUSION_KEEP_AUDIO,
    ):
        try:
            self._fps_limit = max(0, int(fps_limit))
        except Exception:
            self._fps_limit = 0
        self._min_frame_interval = (
            1.0 / self._fps_limit if self._fps_limit > 0 else 0.0
        )
        self._last_frame_t = 0.0

        if quality not in ("high", "balanced", "performance"):
            quality = "high"
        self._quality = quality
        try:
            self.canvas.set_render_quality(quality)
        except Exception:
            pass

        try:
            self._occlusion_stop_percent = max(0, min(100, int(occlusion_stop_percent)))
        except Exception:
            self._occlusion_stop_percent = DEFAULT_OCCLUSION_STOP_PERCENT
        self._keep_audio_when_occluded = bool(occlusion_keep_audio)

        self._apply_audio_for_occlusion()

    def _check_occlusion(self):
        if not self.isVisible() or self.isMinimized():
            return
        hwnd = int(self.winId())
        try:
            if self._occlusion_stop_percent <= 0:
                occluded = False
            elif self._occlusion_stop_percent >= 100:
                ratio = get_occlusion_ratio(hwnd)
                occluded = ratio >= 0.995
            else:
                ratio = get_occlusion_ratio(hwnd)
                occluded = ratio >= self._occlusion_stop_percent / 100.0
        except Exception:
            return

        if occluded != self._occluded:
            self._occluded = occluded
            if occluded:
                try:
                    self.canvas._cached = None
                    self.canvas._cached_size = None
                except Exception:
                    pass
            self._apply_audio_for_occlusion()

    def _apply_audio_for_occlusion(self):
        try:
            if self._occluded and not self._keep_audio_when_occluded:
                self.audio_output.setMuted(True)
            else:
                self.audio_output.setMuted(False)
        except Exception:
            pass
        self._update_memory_state()

    def _should_release_memory(self) -> bool:
        if not self._occluded:
            return False
        if not self._keep_audio_when_occluded:
            return True
        if not self._has_audio:
            return True
        try:
            if self.audio_output.isMuted():
                return True
            if self.audio_output.volume() <= 0.001:
                return True
        except Exception:
            pass
        return False

    def _update_memory_state(self):
        try:
            should_release = self._should_release_memory()
        except Exception:
            return
        if should_release and not self._released:
            self._release_media()
        elif not should_release and self._released:
            self._reload_media()

    def _release_media(self):
        if self._released:
            return
        self._released = True
        try:
            self._saved_position = int(self.player.position())
        except Exception:
            self._saved_position = 0
        try:
            self.player.stop()
            self.player.setSource(QUrl())
        except Exception:
            pass
        try:
            self.canvas.clear_frames()
        except Exception:
            pass

    def _reload_media(self):
        if not self._released:
            return
        self._released = False
        try:
            self.player.setSource(QUrl.fromLocalFile(self.video_path))
        except Exception:
            pass

    def _on_frame(self, frame):
        if self._released:
            return
        if self._dragging or self._occluded:
            return
        if not frame.isValid():
            return

        if self._fps_limit > 0:
            now = time.perf_counter()
            if now - self._last_frame_t < self._min_frame_interval:
                return
            self._last_frame_t = now

        self.canvas.set_frame(frame.toImage())

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            try:
                self._has_audio = bool(self.player.hasAudio())
            except Exception:
                self._has_audio = True

            if self._saved_position > 0:
                try:
                    self.player.setPosition(self._saved_position)
                except Exception:
                    pass
                self._saved_position = 0

            try:
                self.player.play()
            except Exception:
                pass

            QTimer.singleShot(0, self._update_memory_state)

        elif status == QMediaPlayer.MediaStatus.EndOfMedia and not self._loop:
            self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape and not self._locked:
            self.close()
        else:
            super().keyPressEvent(e)

    def snapshot_config(self):
        geo = self.geometry()
        return {
            "video": self.video_name, "loop": self._loop,
            "x": geo.x(), "y": geo.y(),
            "width": geo.width(), "height": geo.height(),
            "radius": self.radius,
            "volume": round(self.audio_output.volume(), 3),
            "opacity": round(self.windowOpacity(), 3),
            "draggable": self._draggable,
            "layer": self._layer,
            "border": self.border_type,
            "border_width": self.border_width_px,
            "border_color": self.border_color,
        }

    def closeEvent(self, event):
        self._bottom_timer.stop()
        try:
            self._occlusion_timer.stop()
        except Exception:
            pass
        try:
            self.sink.videoFrameChanged.disconnect(self._on_frame)
        except Exception:
            pass
        try:
            self.canvas.clear_frames()
        except Exception:
            pass
        try:
            self.player.stop()
            self.player.setSource(QUrl())
        except Exception:
            pass
        try:
            self.player.deleteLater()
        except Exception:
            pass
        try:
            self.audio_output.deleteLater()
            self.sink.deleteLater()
        except Exception:
            pass
        self.closed.emit(self)
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
# 预览窗口
# ═══════════════════════════════════════════════════════════════════════════
@themed
class PreviewWindow(QWidget):
    saved = pyqtSignal(dict)
    cancelled = pyqtSignal()
    RESIZE_MARGIN = 6
    MIN_W = 500
    MIN_H = 380
    RADIUS_MAX = 500
    MAX_W = 3840
    MAX_H = 2160

    def __init__(self, cfg, video_path=None, parent=None):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self.setMouseTracking(True)

        self.radius = max(0, min(self.RADIUS_MAX, int(cfg.get('radius', 12))))
        self.opacity = max(0.1, min(1.0, float(cfg.get('opacity', 1.0))))
        self.border_type = int(cfg.get('border', BORDER_NONE))
        self.border_width_px = int(cfg.get(
            'border_width', BORDER_DEFAULT_WIDTH.get(self.border_type, 10)
        ))
        self._border_color = cfg.get('border_color', DEFAULT_BORDER_COLOR)

        x = int(cfg.get('x', 200)); y = int(cfg.get('y', 200))
        w = max(self.MIN_W, int(cfg.get('width', 800)))
        h = max(self.MIN_H, int(cfg.get('height', 540)))
        self.setGeometry(x, y, w, h)
        self.setWindowOpacity(self.opacity)

        self._drag_start = None; self._window_start = None
        self._resizing = False; self._resize_edge = Qt.Edge(0)
        self._start_geo = None; self._start_mouse = None
        self._saved_once = False
        self._cancelled = False

        self._video_path = video_path
        self._video_aspect = None
        self._video_resolution = None
        self._aspect_locked = False
        self._locked_aspect = None
        self._probe_player = None
        self._probe_audio = None
        self._probe_sink = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addStretch(1)

        panel = QWidget(self)
        panel.setObjectName("previewPanel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setFixedWidth(460)
        panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._preview_panel = panel
        self._apply_theme_colors()

        pl = QVBoxLayout(panel)
        pl.setContentsMargins(22, 18, 22, 18)
        pl.setSpacing(10)

        row = QHBoxLayout(); row.setSpacing(12)
        row.addWidget(BodyLabel("宽度"))
        self.w_spin = SpinBox()
        self.w_spin.setRange(self.MIN_W, self.MAX_W)
        self.w_spin.setValue(self.width())
        self.w_spin.valueChanged.connect(self._on_w_changed)
        row.addWidget(self.w_spin, 1)
        pl.addLayout(row)

        row = QHBoxLayout(); row.setSpacing(12)
        row.addWidget(BodyLabel("高度"))
        self.h_spin = SpinBox()
        self.h_spin.setRange(self.MIN_H, self.MAX_H)
        self.h_spin.setValue(self.height())
        self.h_spin.valueChanged.connect(self._on_h_changed)
        row.addWidget(self.h_spin, 1)
        pl.addLayout(row)

        row = QHBoxLayout(); row.setSpacing(12)
        row.addWidget(BodyLabel("锁定宽高比"))
        self.aspect_info = CaptionLabel("未锁定")
        row.addWidget(self.aspect_info)
        row.addStretch(1)
        self.aspect_switch = SwitchButton()
        self.aspect_switch.checkedChanged.connect(self._on_aspect_toggle)
        row.addWidget(self.aspect_switch)
        pl.addLayout(row)

        hint = CaptionLabel("提示：可用鼠标拖动窗口边框直接调节窗口大小")
        hint.setWordWrap(True)
        pl.addWidget(hint)

        row = QHBoxLayout(); row.setSpacing(12)
        row.addWidget(BodyLabel("圆角"))
        self.radius_slider = Slider(Qt.Orientation.Horizontal)
        self.radius_slider.setRange(0, self.RADIUS_MAX)
        self.radius_slider.setValue(self.radius)
        self.radius_slider.valueChanged.connect(self._on_radius)
        row.addWidget(self.radius_slider, 1)
        self.radius_val = CaptionLabel(str(self.radius))
        self.radius_val.setFixedWidth(50)
        self.radius_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.radius_val)
        pl.addLayout(row)

        row = QHBoxLayout(); row.setSpacing(12)
        row.addWidget(BodyLabel("透明度"))
        self.opacity_slider = Slider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(self.opacity * 100))
        self.opacity_slider.valueChanged.connect(self._on_opacity)
        row.addWidget(self.opacity_slider, 1)
        self.opacity_val = CaptionLabel(f"{int(self.opacity * 100)}%")
        self.opacity_val.setFixedWidth(50)
        self.opacity_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.opacity_val)
        pl.addLayout(row)

        row = QHBoxLayout(); row.setSpacing(12)
        row.addWidget(BodyLabel("边框"))
        self.border_combo = FluentComboBox()
        self.border_combo.addItems(BORDER_LABELS)
        self.border_combo.setCurrentIndex(self.border_type)
        self.border_combo.currentIndexChanged.connect(self._on_border_changed)
        row.addWidget(self.border_combo, 1)
        self.color_btn = PushButton(self._border_color)
        self.color_btn.setFixedWidth(90)
        self.color_btn.clicked.connect(self._pick_border_color)
        row.addWidget(self.color_btn)
        pl.addLayout(row)

        row = QHBoxLayout(); row.setSpacing(12)
        row.addWidget(BodyLabel("边框宽度"))
        self.border_w_slider = Slider(Qt.Orientation.Horizontal)
        self.border_w_slider.setRange(0, 60)
        self.border_w_slider.setValue(self.border_width_px)
        self.border_w_slider.valueChanged.connect(self._on_border_width)
        row.addWidget(self.border_w_slider, 1)
        self.border_w_val = CaptionLabel(str(self.border_width_px))
        self.border_w_val.setFixedWidth(50)
        self.border_w_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.border_w_val)
        pl.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch(1)
        cancel_btn = PushButton("取消")
        cancel_btn.setFixedSize(110, 36)
        cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.addWidget(cancel_btn)
        save_btn = PrimaryPushButton("保存配置")
        save_btn.setFixedSize(110, 36)
        save_btn.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(save_btn)
        pl.addLayout(btn_row)

        panel_row = QHBoxLayout()
        panel_row.addStretch(1)
        panel_row.addWidget(panel)
        panel_row.addStretch(1)
        root.addLayout(panel_row)
        root.addStretch(1)

        self._update_border_w_enabled()
        self._update_color_btn()

        QTimer.singleShot(0, self._apply_win32_styles)

        if self._video_path and os.path.exists(self._video_path):
            QTimer.singleShot(0, self._start_probe_video)

    def _apply_theme_colors(self):
        if not hasattr(self, "_preview_panel"):
            return
        panel_bg = THEME.color("panel_bg")
        panel_border = THEME.color("panel_border")
        text = THEME.color("text")
        self._preview_panel.setStyleSheet(f"""
            #previewPanel {{
                background-color: {panel_bg};
                border: 1px solid {panel_border};
                border-radius: 10px;
            }}
            #previewPanel QLabel {{
                background: transparent;
                color: {text};
            }}
        """)

    def _on_theme_changed(self):
        self._apply_theme_colors()

    def _start_probe_video(self):
        try:
            self._probe_player = QMediaPlayer(self)
            self._probe_audio = QAudioOutput(self)
            self._probe_audio.setMuted(True)
            self._probe_audio.setVolume(0.0)
            self._probe_player.setAudioOutput(self._probe_audio)
            self._probe_sink = QVideoSink(self)
            self._probe_player.setVideoSink(self._probe_sink)
            self._probe_sink.videoFrameChanged.connect(self._on_probe_frame)
            self._probe_player.setSource(QUrl.fromLocalFile(self._video_path))
            self._probe_player.play()
        except Exception as e:
            print(f"[探测视频分辨率失败] {e}")

    def _on_probe_frame(self, frame):
        try:
            if frame.isValid():
                img = frame.toImage()
                w, h = img.width(), img.height()
                if w > 0 and h > 0:
                    self._video_aspect = w / h
                    self._video_resolution = (w, h)
                    if self._aspect_locked and self.aspect_switch.isChecked():
                        self._locked_aspect = self._video_aspect
                        self.aspect_info.setText(self._fmt_aspect(self._video_aspect))
                        g = self.geometry()
                        new_h = max(self.MIN_H, min(self.MAX_H,
                                                    int(round(g.width() / self._video_aspect))))
                        self._apply_size(g.width(), new_h)
        except Exception:
            pass
        try:
            self._probe_sink.videoFrameChanged.disconnect(self._on_probe_frame)
        except Exception:
            pass
        try:
            self._probe_player.stop()
            self._probe_player.setSource(QUrl())
        except Exception:
            pass

    def _apply_win32_styles(self):
        hwnd = int(self.winId())
        setup_frameless_window(hwnd)
        set_tool_window(hwnd)

    def _update_border_w_enabled(self):
        idx = self.border_combo.currentIndex()
        self.border_w_slider.setEnabled(idx != BORDER_NONE)
        if hasattr(self, 'color_btn'):
            self.color_btn.setEnabled(idx == BORDER_SOLID)

    def _update_color_btn(self):
        if not hasattr(self, 'color_btn'):
            return
        self.color_btn.setText(self._border_color)

    def _pick_border_color(self):
        c = QColorDialog.getColor(QColor(self._border_color), self,
                                  "选择边框颜色")
        if c.isValid():
            self._border_color = c.name()
            self._update_color_btn()
            self.update()

    def _on_radius(self, v):
        self.radius = int(v)
        self.radius_val.setText(str(v))
        self.update()

    def _on_opacity(self, v):
        self.opacity = v / 100.0
        self.opacity_val.setText(f"{v}%")
        self.setWindowOpacity(self.opacity)

    def _on_border_changed(self, idx):
        self.border_type = int(idx)
        self._update_border_w_enabled()
        self.update()

    def _on_border_width(self, v):
        self.border_width_px = int(v)
        self.border_w_val.setText(str(v))
        self.update()

    def _on_save_clicked(self):
        self._saved_once = True
        self.saved.emit(self._values())
        self.close()

    def _on_cancel_clicked(self):
        self._cancelled = True
        self.close()

    def _values(self):
        g = self.geometry()
        return {
            'x': g.x(), 'y': g.y(),
            'width': g.width(), 'height': g.height(),
            'radius': self.radius, 'opacity': self.opacity,
            'border': self.border_type, 'border_width': self.border_width_px,
            'border_color': self._border_color,
        }

    def _on_w_changed(self, v):
        if not hasattr(self, 'h_spin'):
            return
        w = int(v)
        h = self.height()
        if self._aspect_locked and self._locked_aspect and self._locked_aspect > 0:
            h = max(self.MIN_H, min(self.MAX_H, int(round(w / self._locked_aspect))))
        self._apply_size(w, h)

    def _on_h_changed(self, v):
        if not hasattr(self, 'w_spin'):
            return
        h = int(v)
        w = self.width()
        if self._aspect_locked and self._locked_aspect and self._locked_aspect > 0:
            w = max(self.MIN_W, min(self.MAX_W, int(round(h * self._locked_aspect))))
        self._apply_size(w, h)

    def _apply_size(self, w, h):
        w = max(self.MIN_W, min(self.MAX_W, int(w)))
        h = max(self.MIN_H, min(self.MAX_H, int(h)))
        g = self.geometry()
        self.setGeometry(g.x(), g.y(), w, h)
        self._sync_inputs(w, h)
        self.update()

    def _sync_inputs(self, w=None, h=None):
        if not hasattr(self, 'w_spin') or not hasattr(self, 'h_spin'):
            return
        if w is None: w = self.width()
        if h is None: h = self.height()
        self.w_spin.blockSignals(True)
        self.h_spin.blockSignals(True)
        self.w_spin.setValue(int(w))
        self.h_spin.setValue(int(h))
        self.w_spin.blockSignals(False)
        self.h_spin.blockSignals(False)

    def _on_aspect_toggle(self, checked: bool):
        if checked:
            aspect = self._video_aspect
            if not aspect or aspect <= 0:
                h = self.height()
                if h > 0:
                    aspect = self.width() / h
            if not aspect or aspect <= 0:
                self._aspect_locked = False
                self._locked_aspect = None
                self.aspect_info.setText("未锁定")
                self.aspect_switch.blockSignals(True)
                self.aspect_switch.setChecked(False)
                self.aspect_switch.blockSignals(False)
                return
            self._locked_aspect = aspect
            self._aspect_locked = True
            self.aspect_info.setText(self._fmt_aspect(aspect))
            g = self.geometry()
            new_h = max(self.MIN_H, min(self.MAX_H, int(round(g.width() / aspect))))
            self._apply_size(g.width(), new_h)
            self._sync_inputs(self.width(), self.height())
        else:
            self._aspect_locked = False
            self._locked_aspect = None
            self.aspect_info.setText("未锁定")

    @staticmethod
    def _fmt_aspect(a):
        if a <= 0:
            return "已锁定"
        common = [
            (16, 9), (16, 10), (4, 3), (21, 9), (32, 9), (3, 2),
            (1, 1), (9, 16), (3, 4), (10, 16), (9, 21),
        ]
        for num, den in common:
            if abs(a - num / den) < 0.02:
                return f"{num}:{den}"
        return f"{a:.2f}"

    def _effective_bw(self):
        if self.border_type == BORDER_NONE:
            return 0
        return max(0, self.border_width_px)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        W, H = self.width(), self.height()
        outer = QRectF(0, 0, W, H)
        bw = self._effective_bw()
        r = max(0.0, min(float(self.radius), W / 2, H / 2))

        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p.fillRect(0, 0, W, H, Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        p.setClipPath(_rounded(outer, r))
        draw_outer_bg(p, outer, r, self.border_type, bw, self._border_color)
        inner = outer.adjusted(bw, bw, -bw, -bw) if bw > 0 else outer
        ir = max(0.0, r - bw) if bw > 0 else r
        p.save()
        p.setClipPath(_rounded(inner, ir), Qt.ClipOperation.ReplaceClip)
        p.fillRect(inner, THEME.qcolor("video_placeholder"))
        p.restore()
        if bw > 0:
            draw_border_ornament(p, outer, inner, r, ir, self.border_type, bw)
        p.end()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not hasattr(self, 'w_spin') or not hasattr(self, 'h_spin'):
            return
        self._sync_inputs(self.width(), self.height())

    def _detect_edge(self, pos):
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self.RESIZE_MARGIN
        edge = Qt.Edge(0)
        if x < m: edge |= Qt.Edge.LeftEdge
        if x > w - m: edge |= Qt.Edge.RightEdge
        if y < m: edge |= Qt.Edge.TopEdge
        if y > h - m: edge |= Qt.Edge.BottomEdge
        return edge

    def _cursor_for_edge(self, edge):
        if edge in (Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
                    Qt.Edge.RightEdge | Qt.Edge.BottomEdge):
            return Qt.CursorShape.SizeFDiagCursor
        if edge in (Qt.Edge.RightEdge | Qt.Edge.TopEdge,
                    Qt.Edge.LeftEdge | Qt.Edge.BottomEdge):
            return Qt.CursorShape.SizeBDiagCursor
        if edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            return Qt.CursorShape.SizeHorCursor
        if edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
            return Qt.CursorShape.SizeVerCursor
        return None

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(e)
        pos = e.position().toPoint()
        edge = self._detect_edge(pos)
        if edge != Qt.Edge(0):
            self._resizing = True
            self._resize_edge = edge
            self._start_geo = QRect(self.geometry())
            self._start_mouse = e.globalPosition().toPoint()
            e.accept(); return
        self._drag_start = e.globalPosition().toPoint()
        self._window_start = self.pos()
        e.accept()

    def mouseMoveEvent(self, e):
        if self._resizing and self._start_geo and self._start_mouse:
            delta = e.globalPosition().toPoint() - self._start_mouse
            edge = self._resize_edge
            start = self._start_geo

            if self._aspect_locked and self._locked_aspect and self._locked_aspect > 0:
                a = self._locked_aspect
                if edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
                    if edge & Qt.Edge.RightEdge:
                        new_w = start.width() + delta.x()
                    else:
                        new_w = start.width() - delta.x()
                    new_w = max(self.MIN_W, min(self.MAX_W, int(new_w)))
                    new_h = max(self.MIN_H, min(self.MAX_H, int(round(new_w / a))))
                    new_w = max(self.MIN_W, min(self.MAX_W, int(round(new_h * a))))
                elif edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
                    if edge & Qt.Edge.BottomEdge:
                        new_h = start.height() + delta.y()
                    else:
                        new_h = start.height() - delta.y()
                    new_h = max(self.MIN_H, min(self.MAX_H, int(new_h)))
                    new_w = max(self.MIN_W, min(self.MAX_W, int(round(new_h * a))))
                    new_h = max(self.MIN_H, min(self.MAX_H, int(round(new_w / a))))
                else:
                    new_w = start.width()
                    new_h = start.height()

                if edge & Qt.Edge.LeftEdge:
                    x = start.right() - new_w + 1
                else:
                    x = start.left()
                if edge & Qt.Edge.TopEdge:
                    y = start.bottom() - new_h + 1
                else:
                    y = start.top()

                self.setGeometry(x, y, new_w, new_h)
                self._sync_inputs(new_w, new_h)
                self.update()
                e.accept()
                return

            g = QRect(start)
            if edge & Qt.Edge.LeftEdge: g.setLeft(g.left() + delta.x())
            if edge & Qt.Edge.RightEdge: g.setRight(g.right() + delta.x())
            if edge & Qt.Edge.TopEdge: g.setTop(g.top() + delta.y())
            if edge & Qt.Edge.BottomEdge: g.setBottom(g.bottom() + delta.y())

            if g.width() < self.MIN_W:
                if edge & Qt.Edge.LeftEdge: g.setLeft(g.right() - self.MIN_W + 1)
                else: g.setRight(g.left() + self.MIN_W - 1)
            if g.height() < self.MIN_H:
                if edge & Qt.Edge.TopEdge: g.setTop(g.bottom() - self.MIN_H + 1)
                else: g.setBottom(g.top() + self.MIN_H - 1)

            self.setGeometry(g)
            self._sync_inputs(g.width(), g.height())
            self.update()
            e.accept()
            return

        pos = e.position().toPoint()
        edge = self._detect_edge(pos)
        cur = self._cursor_for_edge(edge)
        if cur:
            self.setCursor(cur)
        else:
            self.unsetCursor()

        if self._drag_start is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            delta = e.globalPosition().toPoint() - self._drag_start
            self.move(self._window_start + delta)
            self.update()
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._resizing = False
        self._resize_edge = Qt.Edge(0)
        self._start_geo = None
        self._start_mouse = None
        self._drag_start = None
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self._on_cancel_clicked()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, event):
        try:
            if self._probe_player is not None:
                self._probe_player.stop()
                self._probe_player.setSource(QUrl())
        except Exception:
            pass
        if self._cancelled:
            self.cancelled.emit()
        elif not self._saved_once:
            self.saved.emit(self._values())
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
# 快捷键录制框
# ═══════════════════════════════════════════════════════════════════════════
@themed
class HotkeyRecorder(QWidget):
    changed = pyqtSignal(str)

    def __init__(self, initial: str = "", parent=None):
        super().__init__(parent)
        self._hotkey = initial or ""
        self._recording = False
        self.setFixedHeight(36)
        self.setMinimumWidth(220)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._label = QLabel("", self)
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self._label.setContentsMargins(12, 0, 12, 0)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._apply_label_style()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)
        self._refresh_text()

    def _apply_label_style(self):
        self._label.setStyleSheet(
            f"background: transparent; color: {THEME.color('input_text')};"
        )

    def _on_theme_changed(self):
        self._apply_label_style()

    def set_hotkey(self, hk: str):
        self._hotkey = hk or ""
        self._refresh_text()
        self.changed.emit(self._hotkey)

    def hotkey(self):
        return self._hotkey

    def _refresh_text(self):
        if self._recording:
            self._label.setText("按下快捷键...")
        else:
            self._label.setText(self._hotkey if self._hotkey else "未设置（点击录制）")

    def paintEvent(self, event):
        bg = THEME.color("input_bg")
        border = THEME.color("input_focus") if self._recording else THEME.color("input_border")
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5),
            6, 6,
        )
        p.fillPath(path, QColor(bg))
        p.setPen(QPen(QColor(border), 1.5))
        p.drawPath(path)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._start_record(); e.accept(); return
        super().mousePressEvent(e)

    def _start_record(self):
        self._recording = True
        self._refresh_text()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.update()

    def _stop_record(self):
        self._recording = False
        self._refresh_text(); self.update()

    def keyPressEvent(self, e):
        if not self._recording:
            super().keyPressEvent(e); return
        key = e.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Alt,
                   Qt.Key.Key_Shift, Qt.Key.Key_Meta):
            return
        if key == Qt.Key.Key_Escape:
            self._stop_record(); return
        mods = e.modifiers()
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier: parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.AltModifier: parts.append("Alt")
        if mods & Qt.KeyboardModifier.ShiftModifier: parts.append("Shift")
        if mods & Qt.KeyboardModifier.MetaModifier: parts.append("Win")
        main = self._key_to_str(key)
        if main: parts.append(main)
        if len(parts) < 2:
            self._label.setText("需含 Ctrl/Alt/Shift/Win")
            QTimer.singleShot(1200, self._refresh_text)
            return
        self._hotkey = "+".join(parts)
        self._stop_record()
        self.changed.emit(self._hotkey)

    def focusOutEvent(self, e):
        if self._recording:
            self._stop_record()
        super().focusOutEvent(e)

    @staticmethod
    def _key_to_str(key):
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key)
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            return chr(key)
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            return f"F{key - Qt.Key.Key_F1 + 1}"
        mapping = {
            Qt.Key.Key_Space: "Space", Qt.Key.Key_Tab: "Tab",
            Qt.Key.Key_Return: "Enter", Qt.Key.Key_Enter: "Enter",
            Qt.Key.Key_Backspace: "Backspace", Qt.Key.Key_Delete: "Delete",
            Qt.Key.Key_Insert: "Insert", Qt.Key.Key_Home: "Home",
            Qt.Key.Key_End: "End", Qt.Key.Key_PageUp: "PageUp",
            Qt.Key.Key_PageDown: "PageDown", Qt.Key.Key_Up: "Up",
            Qt.Key.Key_Down: "Down", Qt.Key.Key_Left: "Left",
            Qt.Key.Key_Right: "Right", Qt.Key.Key_Plus: "Plus",
            Qt.Key.Key_Minus: "Minus", Qt.Key.Key_Comma: "Comma",
            Qt.Key.Key_Period: "Period", Qt.Key.Key_Slash: "Slash",
            Qt.Key.Key_Semicolon: "Semicolon", Qt.Key.Key_QuoteLeft: "Quote",
            Qt.Key.Key_BracketLeft: "BracketLeft",
            Qt.Key.Key_BracketRight: "BracketRight",
            Qt.Key.Key_Backslash: "Backslash",
        }
        return mapping.get(key, "")


# ═══════════════════════════════════════════════════════════════════════════
# 引导对话框
# ═══════════════════════════════════════════════════════════════════════════
@themed
class OnboardingDialog(QDialog):
    def __init__(self, default_hotkey, parent=None):
        super().__init__(parent)
        self.setObjectName("OnboardingDialog")
        self.setModal(True)
        self.setWindowTitle("欢迎使用")
        self.setFixedSize(600, 500)

        self._hotkey = default_hotkey or ""
        self._skipped = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget(self)
        root.addWidget(self.stack, 1)

        nav = QWidget(self)
        nav_l = QHBoxLayout(nav)
        nav_l.setContentsMargins(24, 12, 24, 16)
        nav_l.setSpacing(10)
        nav_l.addStretch(1)

        self.skip_btn = QPushButton("跳过")
        self.skip_btn.setFixedSize(88, 34)
        self.skip_btn.clicked.connect(self._on_skip)
        nav_l.addWidget(self.skip_btn)

        self.prev_btn = QPushButton("上一步")
        self.prev_btn.setFixedSize(88, 34)
        self.prev_btn.clicked.connect(self._on_prev)
        self.prev_btn.setVisible(False)
        nav_l.addWidget(self.prev_btn)

        self.next_btn = QPushButton("下一步")
        self.next_btn.setFixedSize(96, 34)
        self.next_btn.clicked.connect(self._on_next)
        nav_l.addWidget(self.next_btn)
        root.addWidget(nav)

        self._build_page1()
        self._build_page2()
        self._update_nav()

        self._on_theme_changed()
        QTimer.singleShot(0, self._center_on_screen)
        QTimer.singleShot(0, lambda: set_win11_round_corner(int(self.winId())))

    def _on_theme_changed(self):
        bg = THEME.color("window_bg")
        self.setStyleSheet(
            f"QDialog#OnboardingDialog {{ background-color: {bg}; }}"
        )
        self._update_title_bar()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._update_title_bar)

    def _update_title_bar(self):
        try:
            hwnd = int(self.winId())
            set_title_bar_dark(hwnd, THEME.is_dark())
        except Exception:
            pass

    def _center_on_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        w = self.frameGeometry().width()
        h = self.frameGeometry().height()
        self.move(
            geo.x() + (geo.width() - w) // 2,
            geo.y() + (geo.height() - h) // 2,
        )

    def _build_page1(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 20)
        layout.setSpacing(10)
        layout.addWidget(TitleLabel("使用说明"))
        layout.addSpacing(4)
        lines = [
            "· 导入视频：点击「导入视频」按钮，视频复制到 video/ 目录",
            "· 新建配置：选择视频 + 边框 + 大小/位置/圆角/音量/透明度",
            "· 运行配置：在配置列表点 ▶ 播放；点 ✕ 关闭",
            "· 视频列表：直接点 ▶ 用默认配置临时播放",
            "· 桌面预览：配置对话框点「桌面预览」在桌面调参",
            "· 层级：桌面层（桌面之上、用户窗口之下）、普通层、顶层",
            "· 锁定：勾选后窗口固定顶层，禁止拖动",
            "· 配置文件存放在 data/ 目录，每个配置一个 JSON 文件",
            "· 默认被遮挡不播放视频仅播放音频释放cpu，视频静音时同时释放内存",
            "· 支持 跟随系统 / 浅色 / 深色 三种主题，设置页可切换",
            "· hello1145版权所有",
        ]
        for line in lines:
            lb = BodyLabel(line)
            lb.setWordWrap(True)
            layout.addWidget(lb)
        layout.addStretch(1)
        self.stack.addWidget(page)

    def _build_page2(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 20)
        layout.setSpacing(12)
        layout.addWidget(TitleLabel("配置快捷键"))
        layout.addWidget(BodyLabel(
            "设置一个全局快捷键，用于一键关闭所有视频播放窗口。\n"
            "点击下方录制框后，直接按下组合键即可自动识别。"
        ))
        layout.addSpacing(10)
        layout.addWidget(BodyLabel("当前快捷键："))
        self.hotkey_recorder = HotkeyRecorder(self._hotkey)
        self.hotkey_recorder.changed.connect(self._on_hotkey_changed)
        layout.addWidget(self.hotkey_recorder)
        hint = CaptionLabel("提示：快捷键需含至少一个修饰键（Ctrl / Alt / Shift / Win）")
        layout.addWidget(hint)
        clr_row = QHBoxLayout()
        clr_row.addStretch(1)
        clr_btn = QPushButton("清除快捷键")
        clr_btn.setFixedSize(110, 30)
        clr_btn.clicked.connect(self._clear_hotkey)
        clr_row.addWidget(clr_btn)
        layout.addLayout(clr_row)
        layout.addStretch(1)
        self.stack.addWidget(page)

    def _on_hotkey_changed(self, hk):
        self._hotkey = hk

    def _clear_hotkey(self):
        self._hotkey = ""
        self.hotkey_recorder.set_hotkey("")

    def _on_prev(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self.stack.setCurrentIndex(idx - 1)
            self._update_nav()

    def _on_next(self):
        idx = self.stack.currentIndex()
        if idx < self.stack.count() - 1:
            self.stack.setCurrentIndex(idx + 1)
            self._update_nav()
        else:
            self._finish()

    def _update_nav(self):
        idx = self.stack.currentIndex()
        self.prev_btn.setVisible(idx > 0)
        self.next_btn.setText("完成" if idx == self.stack.count() - 1 else "下一步")

    def _on_skip(self):
        self._skipped = True
        self.accept()

    def _finish(self):
        self.accept()

    def hotkey(self):
        return self._hotkey

    def skipped(self):
        return self._skipped

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_next()
            return
        if e.key() == Qt.Key.Key_Escape:
            self._on_skip()
            return
        super().keyPressEvent(e)


# ═══════════════════════════════════════════════════════════════════════════
# 配置对话框
# ═══════════════════════════════════════════════════════════════════════════
@themed
class ConfigDialog(QDialog):
    CTRL_H = 32

    def __init__(self, config_name, video_name, cfg, all_videos,
                 save_callback=None, parent=None):
        super().__init__(parent)
        self.setObjectName("ConfigDialog")
        self.setWindowTitle(f"配置 - {config_name}")
        self.setWindowFlags(Qt.WindowType.Dialog)
        self.setMinimumSize(560, 720)
        self.resize(580, 760)

        self.cfg = dict(cfg)
        self.config_name = config_name
        self._save_callback = save_callback
        self._saved = False
        self._preview_win = None
        self._preview_active = False
        self._border_color = cfg.get('border_color', DEFAULT_BORDER_COLOR)

        main = QVBoxLayout(self)
        main.setContentsMargins(28, 24, 28, 24)
        main.setSpacing(12)

        t = TitleLabel(f"配置：{config_name}")
        t.setMinimumHeight(40)
        main.addWidget(t)

        self.video_combo = FluentComboBox()
        self.video_combo.addItems(all_videos)
        if video_name in all_videos:
            self.video_combo.setCurrentText(video_name)
        self.video_combo.setFixedHeight(self.CTRL_H)
        main.addLayout(self._row("视频文件", self.video_combo))

        self.loop_switch = SwitchButton()
        self.loop_switch.setChecked(bool(cfg.get('loop', True)))
        main.addLayout(self._row_switch("循环播放", self.loop_switch))

        self.drag_switch = SwitchButton()
        self.drag_switch.setChecked(bool(cfg.get('draggable', True)))
        main.addLayout(self._row_switch("允许拖动窗口", self.drag_switch))

        self.x_spin = self._make_spin(int(cfg.get('x', 120)), -10000, 10000)
        self.y_spin = self._make_spin(int(cfg.get('y', 120)), -10000, 10000)
        main.addLayout(self._row_xy("窗口位置", "X", self.x_spin, "Y", self.y_spin))

        self.w_spin = self._make_spin(int(cfg.get('width', 900)), 200, 10000)
        self.h_spin = self._make_spin(int(cfg.get('height', 540)), 120, 10000)
        main.addLayout(self._row_xy("窗口大小", "宽", self.w_spin, "高", self.h_spin))

        row = QHBoxLayout(); row.setSpacing(12)
        row.addWidget(self._make_label("边框样式"))
        self.border_combo = FluentComboBox()
        self.border_combo.addItems(BORDER_LABELS)
        self.border_combo.setCurrentIndex(int(cfg.get('border', BORDER_NONE)))
        self.border_combo.setFixedHeight(self.CTRL_H)
        self.border_combo.currentIndexChanged.connect(self._on_border_type_changed)
        row.addWidget(self.border_combo, 1)
        self.color_btn = PushButton(self._border_color)
        self.color_btn.setFixedSize(110, self.CTRL_H)
        self.color_btn.clicked.connect(self._pick_border_color)
        row.addWidget(self.color_btn)
        main.addLayout(row)

        self.border_w_slider = self._make_slider(0, 60, int(cfg.get('border_width', 10)))
        self.border_w_label = self._make_value_label(str(self.border_w_slider.value()))
        main.addLayout(self._row_slider("边框宽度", self.border_w_slider, self.border_w_label))
        self.border_w_slider.valueChanged.connect(
            lambda v: self.border_w_label.setText(str(v))
        )

        self.radius_slider = self._make_slider(0, PreviewWindow.RADIUS_MAX,
                                                int(cfg.get('radius', 12)))
        self.radius_label = self._make_value_label(str(self.radius_slider.value()), 60)
        main.addLayout(self._row_slider("圆角半径", self.radius_slider, self.radius_label))
        self.radius_slider.valueChanged.connect(
            lambda v: self.radius_label.setText(str(v))
        )

        self.volume_slider = self._make_slider(0, 100, int(cfg.get('volume', 0.8) * 100))
        self.volume_label = self._make_value_label(f"{self.volume_slider.value()}%")
        main.addLayout(self._row_slider("音量", self.volume_slider, self.volume_label))
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_label.setText(f"{v}%")
        )

        self.opacity_slider = self._make_slider(10, 100, int(cfg.get('opacity', 1.0) * 100))
        self.opacity_label = self._make_value_label(f"{self.opacity_slider.value()}%")
        main.addLayout(self._row_slider("透明度", self.opacity_slider, self.opacity_label))
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_label.setText(f"{v}%")
        )

        main.addStretch(1)

        btns = QHBoxLayout()
        btns.setSpacing(12)

        self.preview_btn = PushButton(FIF.VIEW, "桌面预览")
        self.preview_btn.setFixedSize(130, 36)
        self.preview_btn.clicked.connect(self._on_preview)
        btns.addWidget(self.preview_btn)

        btns.addStretch(1)
        cancel = PushButton("取消")
        cancel.setFixedSize(100, 36)
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)

        save = PrimaryPushButton("保存")
        save.setFixedSize(100, 36)
        save.clicked.connect(self._on_save_clicked)
        btns.addWidget(save)
        main.addLayout(btns)

        self._update_border_w_enabled()
        self._update_color_btn()

        self._on_theme_changed()

    def _on_theme_changed(self):
        bg = THEME.color("window_bg")
        self.setStyleSheet(
            f"QDialog#ConfigDialog {{ background-color: {bg}; }}"
        )
        self._update_title_bar()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._update_title_bar)

    def _update_title_bar(self):
        try:
            hwnd = int(self.winId())
            set_title_bar_dark(hwnd, THEME.is_dark())
        except Exception:
            pass

    def _on_border_type_changed(self, idx):
        self._update_border_w_enabled()

    def _update_border_w_enabled(self):
        idx = self.border_combo.currentIndex()
        self.border_w_slider.setEnabled(idx != BORDER_NONE)
        if hasattr(self, 'color_btn'):
            self.color_btn.setEnabled(idx == BORDER_SOLID)

    def _update_color_btn(self):
        if not hasattr(self, 'color_btn'):
            return
        self.color_btn.setText(self._border_color)

    def _pick_border_color(self):
        c = QColorDialog.getColor(QColor(self._border_color), self,
                                  "选择边框颜色")
        if c.isValid():
            self._border_color = c.name()
            self._update_color_btn()

    def _on_save_clicked(self):
        try:
            cfg_data = self.get_config()
        except Exception as e:
            InfoBar.error("获取配置失败", str(e), parent=self, duration=4000)
            return

        if self._save_callback is not None:
            try:
                ok, info = self._save_callback(cfg_data)
            except Exception as e:
                InfoBar.error("保存异常", str(e), parent=self, duration=5000)
                return

            if ok:
                self._saved = True
                InfoBar.success(
                    "配置已保存",
                    f"data/{self.config_name}.json",
                    parent=self, duration=1500,
                )
                QTimer.singleShot(250, self.accept)
            else:
                InfoBar.error(
                    "保存失败", str(info),
                    parent=self, duration=5000,
                )
        else:
            self._saved = True
            self.accept()

    def was_saved(self) -> bool:
        return self._saved

    def _on_preview(self):
        if self._preview_win is not None:
            try:
                self._preview_win.raise_()
                self._preview_win.activateWindow()
                return
            except RuntimeError:
                self._preview_win = None

        main_win = self.parent()

        skip = set()
        for w in (self, main_win):
            if w is not None:
                try:
                    skip.add(int(w.winId()))
                except Exception:
                    pass

        minimize_other_windows(skip)
        self.setVisible(False)

        cfg_data = self.get_config()
        video_name = cfg_data.get('video', '')
        video_path = None
        if video_name:
            candidate = os.path.join(get_video_dir(), video_name)
            if os.path.exists(candidate):
                video_path = candidate

        self._preview_win = PreviewWindow(cfg_data, video_path=video_path)
        self._preview_win.saved.connect(self._on_preview_closed)
        self._preview_win.cancelled.connect(self._on_preview_cancelled)
        self._preview_active = True
        self._preview_win.show()
        self._preview_win.raise_()
        self._preview_win.activateWindow()

    def _on_preview_closed(self, values):
        self._apply_preview_values(values)
        self._restore_from_preview()

    def _on_preview_cancelled(self):
        self._restore_from_preview()

    def _restore_from_preview(self):
        self.setVisible(True)
        self.setWindowState(
            (self.windowState() & ~Qt.WindowState.WindowMinimized)
            | Qt.WindowState.WindowActive
        )
        self.raise_()
        self.activateWindow()
        self._preview_win = None
        self._preview_active = False

    def _apply_preview_values(self, values):
        self.x_spin.setValue(int(values['x']))
        self.y_spin.setValue(int(values['y']))
        self.w_spin.setValue(int(values['width']))
        self.h_spin.setValue(int(values['height']))
        self.radius_slider.setValue(int(values['radius']))
        self.opacity_slider.setValue(int(round(values['opacity'] * 100)))
        if 'border' in values:
            self.border_combo.setCurrentIndex(int(values['border']))
        if 'border_width' in values:
            self.border_w_slider.setValue(int(values['border_width']))
        if 'border_color' in values:
            self._border_color = values['border_color']
            self._update_color_btn()

    def _make_spin(self, value, lo, hi):
        s = SpinBox()
        s.setRange(lo, hi); s.setValue(value)
        s.setFixedHeight(self.CTRL_H); s.setFixedWidth(140)
        return s

    def _make_slider(self, lo, hi, value):
        s = Slider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi); s.setValue(value)
        s.setFixedHeight(self.CTRL_H)
        return s

    def _make_value_label(self, text, w=56):
        lbl = BodyLabel(text)
        lbl.setFixedSize(w, self.CTRL_H)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    def _make_label(self, text, width=96):
        lbl = BodyLabel(text)
        lbl.setMinimumWidth(width)
        lbl.setFixedHeight(self.CTRL_H)
        lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        return lbl

    def _row(self, label_text, widget):
        r = QHBoxLayout(); r.setSpacing(12)
        r.addWidget(self._make_label(label_text))
        r.addWidget(widget, 1)
        return r

    def _row_switch(self, label_text, switch):
        r = QHBoxLayout(); r.setSpacing(12)
        r.addWidget(self._make_label(label_text, 160))
        r.addStretch(1); r.addWidget(switch)
        return r

    def _row_xy(self, label_text, la, wa, lb, wb):
        r = QHBoxLayout(); r.setSpacing(10)
        r.addWidget(self._make_label(label_text, 96))
        r.addWidget(self._make_label(la, 24)); r.addWidget(wa)
        r.addSpacing(12)
        r.addWidget(self._make_label(lb, 24)); r.addWidget(wb)
        r.addStretch(1)
        return r

    def _row_slider(self, label_text, slider, value_label):
        r = QHBoxLayout(); r.setSpacing(12)
        r.addWidget(self._make_label(label_text, 96))
        r.addWidget(slider, 1); r.addWidget(value_label)
        return r

    def get_config(self) -> dict:
        return {
            "video": self.video_combo.currentText(),
            "loop": self.loop_switch.isChecked(),
            "x": int(self.x_spin.value()),
            "y": int(self.y_spin.value()),
            "width": int(self.w_spin.value()),
            "height": int(self.h_spin.value()),
            "radius": int(self.radius_slider.value()),
            "volume": round(self.volume_slider.value() / 100.0, 3),
            "opacity": round(self.opacity_slider.value() / 100.0, 3),
            "draggable": self.drag_switch.isChecked(),
            "layer": 0,
            "border": int(self.border_combo.currentIndex()),
            "border_width": int(self.border_w_slider.value()),
            "border_color": self._border_color,
        }

    def closeEvent(self, event):
        if self._preview_active:
            try:
                if self._preview_win is not None:
                    self._preview_win.close()
            except RuntimeError:
                pass
            self._preview_active = False
            self._preview_win = None
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
# 配置卡片 / 视频卡片
# ═══════════════════════════════════════════════════════════════════════════
@themed
class ConfigCard(QWidget):
    runClicked = pyqtSignal(str)
    editClicked = pyqtSignal(str)
    deleteClicked = pyqtSignal(str)

    def __init__(self, name, cfg, playing, parent=None):
        super().__init__(parent)
        self.name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        n = StrongBodyLabel(name); n.setMinimumWidth(110)
        layout.addWidget(n)
        v = BodyLabel(cfg.get('video', '—') or '—'); v.setMinimumWidth(180)
        layout.addWidget(v)

        b = int(cfg.get('border', BORDER_NONE))
        b_label = BORDER_LABELS[b] if 0 <= b < len(BORDER_LABELS) else "—"
        b_w = int(cfg.get('border_width', 10))
        b_txt = b_label + (f"({b_w}px)" if b != BORDER_NONE else "")

        info = CaptionLabel(
            f"{cfg.get('width', 900)}×{cfg.get('height', 540)}  "
            f"圆角 {cfg.get('radius', 12)}  "
            f"音量 {int(cfg.get('volume', 0.8) * 100)}%  "
            f"透明 {int(cfg.get('opacity', 1.0) * 100)}%  "
            f"{b_txt}  "
            f"{'可拖' if cfg.get('draggable', True) else '固定'}"
        )
        layout.addWidget(info, 1)

        edit_btn = ToolButton(FIF.EDIT); edit_btn.setFixedSize(32, 32)
        edit_btn.setToolTip("编辑配置")
        edit_btn.clicked.connect(lambda: self.editClicked.emit(self.name))
        layout.addWidget(edit_btn)

        del_btn = ToolButton(FIF.DELETE); del_btn.setFixedSize(32, 32)
        del_btn.setToolTip("删除配置")
        del_btn.clicked.connect(lambda: self.deleteClicked.emit(self.name))
        layout.addWidget(del_btn)

        self.run_btn = ToolButton(FIF.PLAY if not playing else FIF.CLOSE)
        self.run_btn.setFixedSize(32, 32)
        self.run_btn.setToolTip("运行" if not playing else "关闭")
        self.run_btn.clicked.connect(lambda: self.runClicked.emit(self.name))
        layout.addWidget(self.run_btn)


@themed
class VideoCard(QWidget):
    runClicked = pyqtSignal(str)

    def __init__(self, name, playing, ref_count, parent=None):
        super().__init__(parent)
        self.name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        n = BodyLabel(name); n.setMinimumWidth(240)
        layout.addWidget(n)

        self._info = CaptionLabel("")
        self._ref_count = ref_count
        self._update_info_text()
        layout.addWidget(self._info, 1)

        self.run_btn = ToolButton(FIF.PLAY if not playing else FIF.CLOSE)
        self.run_btn.setFixedSize(32, 32)
        self.run_btn.setToolTip("运行" if not playing else "关闭")
        self.run_btn.clicked.connect(lambda: self.runClicked.emit(self.name))
        layout.addWidget(self.run_btn)

    def _update_info_text(self):
        if self._ref_count:
            self._info.setText(f"被 {self._ref_count} 个配置引用")
            self._info.setStyleSheet(
                f"color: {THEME.color('text_link')}; background: transparent;"
            )
        else:
            self._info.setText("无配置引用（直接运行使用默认配置）")
            self._info.setStyleSheet("")

    def _on_theme_changed(self):
        self._update_info_text()


# ═══════════════════════════════════════════════════════════════════════════
# 主窗口
# ═══════════════════════════════════════════════════════════════════════════
class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("桌面视频播放器")
        self.setWindowIcon(FIF.MOVIE.icon())

        self.setMinimumSize(980, 660)
        self.resize(1180, 820)

        self.data_dir = get_data_dir()
        self.video_dir = get_video_dir()
        self.settings = AppSettings(self.data_dir)
        self.cfg_mgr = ConfigManager(self.data_dir)
        self._playing: dict[str, VideoWindow] = {}
        self._force_quit = False
        self._refreshing = False
        self._refresh_requested = False

        # 应用已保存的主题（auto/light/dark）
        saved_theme = str(self.settings.get('theme_mode', 'auto')).lower()
        if saved_theme not in ("auto", "light", "dark"):
            saved_theme = "auto"
        THEME.set_mode(saved_theme, force=True)

        self._hotkey_filter = HotkeyFilter(self._close_all_videos)
        QApplication.instance().installNativeEventFilter(self._hotkey_filter)
        hk = self.settings.get('hotkey', '')
        if hk:
            self._hotkey_filter.register(hk)

        self.home_page = self._build_home_page()
        self.settings_page = self._build_settings_page()

        self.addSubInterface(
            self.home_page, FIF.HOME, "主界面",
            position=NavigationItemPosition.TOP,
        )
        self.addSubInterface(
            self.settings_page, FIF.SETTING, "设置",
            position=NavigationItemPosition.TOP,
        )

        try:
            self.navigationInterface.setExpandWidth(200)
            self.navigationInterface.setMinimumExpandWidth(600)
            self.navigationInterface.setCollapsible(False)
        except Exception:
            pass

        # 系统主题监听（auto 模式下自动切换）
        self._system_theme_watcher = SystemThemeWatcher(self)

        self._setup_tray()

        self._refresh_all()

        autostart_mode = AUTOSTART_FLAG in sys.argv
        if not self.settings.get('initialized', False) and not autostart_mode:
            QTimer.singleShot(400, self._onboarding)

        QTimer.singleShot(600, self._run_auto_configs_on_startup)

    def start_in_tray(self):
        self.tray_icon.show()

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(FIF.MOVIE.icon())
        self.tray_icon.setToolTip("桌面视频播放器")

        menu = QMenu()
        show_action = QAction("显示主界面", self)
        show_action.triggered.connect(self._show_from_tray)
        menu.addAction(show_action)

        menu.addSeparator()

        close_videos_action = QAction("关闭所有视频", self)
        close_videos_action.triggered.connect(self._close_all_videos)
        menu.addAction(close_videos_action)

        menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)

        self.tray_icon.hide()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible() and not self.isMinimized():
                self._hide_to_tray()
            else:
                self._show_from_tray()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _hide_to_tray(self):
        self.hide()
        if not self.tray_icon.isVisible():
            self.tray_icon.show()

    def _quit_app(self):
        self._force_quit = True
        self._close_all_videos()
        self._cleanup_and_exit()
        self.close()
        QApplication.quit()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized() and self.settings.get('minimize_to_tray', True):
                QTimer.singleShot(0, self._hide_to_tray)

    def _cleanup_and_exit(self):
        try:
            self._hotkey_filter.unregister()
        except Exception:
            pass
        try:
            self.tray_icon.hide()
        except Exception:
            pass

    def closeEvent(self, event):
        if self._force_quit:
            self._cleanup_and_exit()
            super().closeEvent(event)
            return

        if not self._playing:
            self._cleanup_and_exit()
            super().closeEvent(event)
            return

        if self.settings.get('minimize_to_tray', True):
            box = MessageBox(
                "有视频正在播放",
                "是否最小化到系统托盘？\n"
                "选择「退出程序」将关闭所有视频并退出。",
                self,
            )
            box.yesButton.setText("最小化到托盘")
            box.cancelButton.setText("退出程序")

            if box.exec():
                event.ignore()
                self._hide_to_tray()
                self.tray_icon.showMessage(
                    "桌面视频播放器",
                    "程序已最小化到系统托盘，双击图标可恢复",
                    QSystemTrayIcon.MessageIcon.Information,
                    1500,
                )
            else:
                self._force_quit = True
                self._close_all_videos()
                self._cleanup_and_exit()
                super().closeEvent(event)
        else:
            self._close_all_videos()
            self._cleanup_and_exit()
            super().closeEvent(event)

    def _build_home_page(self):
        page = ThemedPage("homePage")
        cl = QVBoxLayout(page)
        cl.setContentsMargins(24, 20, 24, 24)
        cl.setSpacing(12)

        row = QHBoxLayout()
        self.import_btn = PrimaryPushButton(FIF.ADD, "导入视频")
        self.import_btn.setFixedHeight(36); self.import_btn.setMinimumWidth(140)
        self.import_btn.clicked.connect(self._on_import)
        row.addWidget(self.import_btn)

        self.new_cfg_btn = PrimaryPushButton(FIF.SETTING, "新建配置")
        self.new_cfg_btn.setFixedHeight(36); self.new_cfg_btn.setMinimumWidth(140)
        self.new_cfg_btn.clicked.connect(self._on_new_config)
        row.addWidget(self.new_cfg_btn)

        self.refresh_btn = PushButton(FIF.SYNC, "刷新")
        self.refresh_btn.setFixedHeight(36); self.refresh_btn.setMinimumWidth(100)
        self.refresh_btn.clicked.connect(self._refresh_all)
        row.addWidget(self.refresh_btn)

        self.close_all_btn = PushButton(FIF.CLOSE, "关闭所有视频")
        self.close_all_btn.setFixedHeight(36); self.close_all_btn.setMinimumWidth(140)
        self.close_all_btn.clicked.connect(self._close_all_videos)
        row.addWidget(self.close_all_btn)
        row.addStretch()
        cl.addLayout(row)

        self.hk_hint = CaptionLabel("")
        cl.addWidget(self.hk_hint)
        self._update_hk_hint()

        cl.addWidget(SubtitleLabel("配置文件（data/ 目录）"))
        self.cfg_list = ListWidget(); self.cfg_list.setMinimumHeight(160)
        cl.addWidget(self.cfg_list, 2)

        cl.addWidget(SubtitleLabel("视频文件（video/ 目录）"))
        self.vid_list = ListWidget(); self.vid_list.setMinimumHeight(160)
        cl.addWidget(self.vid_list, 2)

        return page

    def _build_settings_page(self):
        page = ThemedPage("settingsPage")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        outer.addWidget(scroll)

        inner = QWidget()
        inner.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        scroll.setWidget(inner)

        cl = QVBoxLayout(inner)
        cl.setContentsMargins(32, 24, 32, 32)
        cl.setSpacing(16)

        cl.addWidget(TitleLabel("设置"))

        # ── 外观（主题）───────────────────────────────────────────────
        cl.addSpacing(8)
        cl.addWidget(SubtitleLabel("外观"))
        theme_card = CardWidget()
        tl = QVBoxLayout(theme_card)
        tl.setContentsMargins(18, 14, 18, 14)
        tl.setSpacing(10)

        r = QHBoxLayout(); r.setSpacing(12)
        lb = BodyLabel("主题模式"); lb.setMinimumWidth(200)
        r.addWidget(lb); r.addStretch(1)
        self.theme_combo = FluentComboBox()
        self.theme_combo.addItems(["跟随系统", "浅色（白天）", "深色（夜间）"])
        _t_map = {"auto": 0, "light": 1, "dark": 2}
        self.theme_combo.setCurrentIndex(_t_map.get(THEME.mode, 0))
        self.theme_combo.setFixedWidth(180); self.theme_combo.setFixedHeight(32)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_combo_changed)
        r.addWidget(self.theme_combo)
        tl.addLayout(r)

        hint_theme = CaptionLabel(
            "「跟随系统」会跟随 Windows 的应用主题自动切换；\n"
            "「浅色」/「深色」强制使用指定主题。\n"
            "切换会立即应用到所有界面并自动保存。"
        )
        hint_theme.setWordWrap(True)
        tl.addWidget(hint_theme)
        cl.addWidget(theme_card)

        # ── 播放 ─────────────────────────────────────────────────────
        cl.addSpacing(8)
        cl.addWidget(SubtitleLabel("播放"))
        play_card = CardWidget()
        pl = QVBoxLayout(play_card)
        pl.setContentsMargins(18, 14, 18, 14)
        pl.setSpacing(10)

        r = QHBoxLayout(); r.setSpacing(12)
        lb = BodyLabel("帧率上限"); lb.setMinimumWidth(200)
        r.addWidget(lb); r.addStretch(1)
        self.fps_combo = FluentComboBox()
        self.fps_combo.addItems(["跟随视频源", "60 FPS", "30 FPS", "24 FPS", "15 FPS"])
        _fps_map = {0: 0, 60: 1, 30: 2, 24: 3, 15: 4}
        _cur_fps = int(self.settings.get('fps_limit', DEFAULT_FPS_LIMIT))
        self.fps_combo.setCurrentIndex(_fps_map.get(_cur_fps, 2))
        self.fps_combo.setFixedWidth(160); self.fps_combo.setFixedHeight(32)
        self.fps_combo.currentIndexChanged.connect(self._on_fps_changed)
        r.addWidget(self.fps_combo)
        pl.addLayout(r)

        r = QHBoxLayout(); r.setSpacing(12)
        lb = BodyLabel("渲染画质"); lb.setMinimumWidth(200)
        r.addWidget(lb); r.addStretch(1)
        self.quality_combo = FluentComboBox()
        self.quality_combo.addItems(["高画质（平滑缩放）", "平衡", "流畅优先"])
        _q_map = {"high": 0, "balanced": 1, "performance": 2}
        _cur_q = str(self.settings.get('render_quality', DEFAULT_RENDER_QUALITY))
        self.quality_combo.setCurrentIndex(_q_map.get(_cur_q, 0))
        self.quality_combo.setFixedWidth(160); self.quality_combo.setFixedHeight(32)
        self.quality_combo.currentIndexChanged.connect(self._on_quality_changed)
        r.addWidget(self.quality_combo)
        pl.addLayout(r)

        r = QHBoxLayout(); r.setSpacing(12)
        lb = BodyLabel("被遮挡多少时停止画面"); lb.setMinimumWidth(200)
        r.addWidget(lb)
        self.occlusion_slider = Slider(Qt.Orientation.Horizontal)
        self.occlusion_slider.setRange(0, 100)
        _cur_occ = int(self.settings.get(
            'occlusion_stop_percent', DEFAULT_OCCLUSION_STOP_PERCENT))
        self.occlusion_slider.setValue(_cur_occ)
        self.occlusion_slider.valueChanged.connect(self._on_occlusion_slider)
        r.addWidget(self.occlusion_slider, 1)
        self.occlusion_label = CaptionLabel(self._fmt_occlusion(_cur_occ))
        self.occlusion_label.setFixedWidth(80)
        self.occlusion_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        r.addWidget(self.occlusion_label)
        pl.addLayout(r)

        r = QHBoxLayout(); r.setSpacing(12)
        lb = BodyLabel("被遮挡停止画面时继续播放声音")
        lb.setMinimumWidth(200)
        r.addWidget(lb); r.addStretch(1)
        self.occlusion_audio_switch = SwitchButton()
        self.occlusion_audio_switch.setChecked(bool(self.settings.get(
            'occlusion_keep_audio', DEFAULT_OCCLUSION_KEEP_AUDIO)))
        self.occlusion_audio_switch.checkedChanged.connect(
            self._on_occlusion_audio_changed)
        r.addWidget(self.occlusion_audio_switch)
        pl.addLayout(r)

        hint = CaptionLabel(
            "帧率上限：超过上限的视频帧会被丢弃（声音照常播放），用于降低 CPU/GPU 占用。\n"
            "遮挡停止：视频被其它窗口遮挡达到该比例时停止刷新画面（声音取决于下方开关）。\n"
            "「100%」= 只有完全被其它窗口遮住时才停止画面；拖到 0 表示永不停止。\n"
            "内存优化：当画面与声音都不需要时（被遮挡且关闭保留声音/静音/无音轨），\n"
            "会自动释放解码器与缓存帧；遮挡解除后从原位置继续播放。"
        )
        hint.setWordWrap(True)
        pl.addWidget(hint)

        cl.addWidget(play_card)

        # ── 窗口行为 ─────────────────────────────────────────────────
        cl.addSpacing(8)
        cl.addWidget(SubtitleLabel("窗口行为"))
        behavior_card = CardWidget()
        bl = QVBoxLayout(behavior_card)
        bl.setContentsMargins(18, 14, 18, 14)
        bl.setSpacing(10)

        r = QHBoxLayout(); r.setSpacing(12)
        lb = BodyLabel("最小化时隐藏到系统托盘")
        lb.setMinimumWidth(200)
        r.addWidget(lb)
        r.addStretch(1)
        self.tray_switch = SwitchButton()
        self.tray_switch.setChecked(bool(self.settings.get('minimize_to_tray', True)))
        self.tray_switch.checkedChanged.connect(self._on_tray_switch_changed)
        r.addWidget(self.tray_switch)
        bl.addLayout(r)

        hint = CaptionLabel(
            "开启后：有视频在播放时关闭主界面会询问是否最小化到托盘；\n"
            "无视频播放时直接退出；关闭本开关则关闭时直接退出。"
        )
        hint.setWordWrap(True)
        bl.addWidget(hint)

        cl.addWidget(behavior_card)

        # ── 开机自启动 ───────────────────────────────────────────────
        cl.addSpacing(8)
        cl.addWidget(SubtitleLabel("开机自启动"))
        auto_card = CardWidget()
        al2 = QVBoxLayout(auto_card)
        al2.setContentsMargins(18, 14, 18, 14)
        al2.setSpacing(10)

        r = QHBoxLayout(); r.setSpacing(12)
        lb = BodyLabel("开机自启动"); lb.setMinimumWidth(200)
        r.addWidget(lb); r.addStretch(1)
        self.autostart_switch = SwitchButton()
        self.autostart_switch.setChecked(is_autostart_enabled())
        self.autostart_switch.checkedChanged.connect(self._on_autostart_changed)
        r.addWidget(self.autostart_switch)
        al2.addLayout(r)

        hint0 = CaptionLabel("开机自启时主界面默认隐藏到系统托盘（仅显示托盘图标）。")
        hint0.setWordWrap(True)
        al2.addWidget(hint0)

        r = QHBoxLayout(); r.setSpacing(12)
        lb = BodyLabel("启动时自动运行配置"); lb.setMinimumWidth(200)
        r.addWidget(lb); r.addStretch(1)
        self.autorun_switch = SwitchButton()
        self.autorun_switch.setChecked(bool(self.settings.get('auto_run_enabled', False)))
        self.autorun_switch.checkedChanged.connect(self._on_autorun_switch_changed)
        r.addWidget(self.autorun_switch)
        al2.addLayout(r)

        hint = CaptionLabel(
            "开启后，程序启动时会自动运行下方勾选的配置。"
            "（未勾选任何配置时不会做任何事）"
        )
        hint.setWordWrap(True)
        al2.addWidget(hint)

        self.autorun_list = QListWidget()
        self.autorun_list.setFixedHeight(150)
        self.autorun_list.itemChanged.connect(self._on_autorun_item_changed)
        al2.addWidget(self.autorun_list)

        cl.addWidget(auto_card)

        # ── 快捷键 ───────────────────────────────────────────────────
        cl.addSpacing(8)
        cl.addWidget(SubtitleLabel("快捷键"))
        hk_card = CardWidget()
        hl = QVBoxLayout(hk_card)
        hl.setContentsMargins(18, 14, 18, 14)
        hl.setSpacing(10)

        r = QHBoxLayout(); r.setSpacing(12)
        lb = BodyLabel("关闭所有视频窗口"); lb.setMinimumWidth(140)
        r.addWidget(lb); r.addStretch(1)
        self.hotkey_recorder = HotkeyRecorder(self.settings.get('hotkey', ''))
        self.hotkey_recorder.changed.connect(self._on_hotkey_recorded)
        r.addWidget(self.hotkey_recorder)
        hl.addLayout(r)

        hint = CaptionLabel(
            "点击录制框后，按下组合键即可自动识别。\n"
            "需包含至少一个修饰键（Ctrl / Alt / Shift / Win）。"
        )
        hint.setWordWrap(True)
        hl.addWidget(hint)

        btn_row = QHBoxLayout(); btn_row.addStretch(1)
        clr_btn = PushButton("清除快捷键"); clr_btn.setFixedSize(110, 32)
        clr_btn.clicked.connect(self._clear_hotkey)
        btn_row.addWidget(clr_btn)
        hl.addLayout(btn_row)

        cl.addWidget(hk_card)

        # ── 关于 ─────────────────────────────────────────────────────
        cl.addSpacing(8)
        cl.addWidget(SubtitleLabel("关于"))
        about_card = CardWidget()
        abl = QVBoxLayout(about_card)
        abl.setContentsMargins(18, 14, 18, 14)
        abl.setSpacing(6)
        abl.addWidget(StrongBodyLabel("桌面视频播放器——hello1145版权所有"))
        abl.addWidget(BodyLabel("基于 PyQt6 + PyQt6-Fluent-Widgets 构建"))
        abl.addWidget(CaptionLabel("配置文件存放在 data/ 目录，视频存放在 video/ 目录"))
        cl.addWidget(about_card)

        cl.addStretch(1)
        return page

    # ── 主题切换 ─────────────────────────────────────────────────────
    def _on_theme_combo_changed(self, idx: int):
        mode = {0: "auto", 1: "light", 2: "dark"}.get(idx, "auto")
        THEME.set_mode(mode, force=True)
        self.settings.set('theme_mode', mode)
        label = {"auto": "跟随系统", "light": "浅色（白天）", "dark": "深色（夜间）"}[mode]
        InfoBar.success("主题已切换", label, parent=self, duration=1500)

    @staticmethod
    def _fmt_occlusion(v: int) -> str:
        if v <= 0:
            return "不停止"
        if v >= 100:
            return "100%"
        return f"{v}%"

    def _on_tray_switch_changed(self, checked: bool):
        self.settings.set('minimize_to_tray', bool(checked))
        if checked:
            InfoBar.success(
                "已开启", "有视频播放时关闭将询问是否最小化到托盘",
                parent=self, duration=1500,
            )
        else:
            InfoBar.info(
                "已关闭", "关闭主界面时直接退出程序",
                parent=self, duration=1500,
            )
            if not self.isMinimized() and self.isVisible():
                self.tray_icon.hide()

    def _on_fps_changed(self, idx: int):
        fps = {0: 0, 1: 60, 2: 30, 3: 24, 4: 15}.get(idx, DEFAULT_FPS_LIMIT)
        self.settings.set('fps_limit', fps)
        self._apply_playback_options_to_playing()
        InfoBar.success(
            "已更新帧率上限",
            "跟随视频源" if fps == 0 else f"{fps} FPS",
            parent=self, duration=1500,
        )

    def _on_quality_changed(self, idx: int):
        q = {0: "high", 1: "balanced", 2: "performance"}.get(
            idx, DEFAULT_RENDER_QUALITY
        )
        self.settings.set('render_quality', q)
        self._apply_playback_options_to_playing()
        InfoBar.success(
            "已更新渲染画质",
            {"high": "高画质", "balanced": "平衡", "performance": "流畅优先"}[q],
            parent=self, duration=1500,
        )

    def _on_occlusion_slider(self, v: int):
        v = int(v)
        self.settings.set('occlusion_stop_percent', v)
        if hasattr(self, 'occlusion_label'):
            self.occlusion_label.setText(self._fmt_occlusion(v))
        self._apply_playback_options_to_playing()

    def _on_occlusion_audio_changed(self, checked: bool):
        self.settings.set('occlusion_keep_audio', bool(checked))
        self._apply_playback_options_to_playing()
        InfoBar.success(
            "已更新",
            "被遮挡停止画面时继续播放声音" if checked
            else "被遮挡停止画面时同时静音",
            parent=self, duration=1500,
        )

    def _apply_playback_options_to_playing(self):
        fps = int(self.settings.get('fps_limit', DEFAULT_FPS_LIMIT))
        q = str(self.settings.get('render_quality', DEFAULT_RENDER_QUALITY))
        occ = int(self.settings.get(
            'occlusion_stop_percent', DEFAULT_OCCLUSION_STOP_PERCENT))
        keep = bool(self.settings.get(
            'occlusion_keep_audio', DEFAULT_OCCLUSION_KEEP_AUDIO))
        for w in list(self._playing.values()):
            try:
                w.set_playback_options(fps, q, occ, keep)
            except RuntimeError:
                pass

    def _on_autostart_changed(self, checked: bool):
        ok, err = set_autostart_enabled(bool(checked))
        if ok:
            self.settings.set('auto_start', bool(checked))
            InfoBar.success(
                "已开启" if checked else "已关闭",
                "程序将随系统启动（启动时默认最小化到托盘）" if checked
                else "已取消开机自启动",
                parent=self, duration=2000,
            )
        else:
            self.autostart_switch.blockSignals(True)
            self.autostart_switch.setChecked(not checked)
            self.autostart_switch.blockSignals(False)
            InfoBar.error("设置失败", err or "无法写入注册表",
                          parent=self, duration=3000)

    def _on_autorun_switch_changed(self, checked: bool):
        self.settings.set('auto_run_enabled', bool(checked))
        if hasattr(self, 'autorun_list'):
            self.autorun_list.setEnabled(bool(checked))
        if checked:
            InfoBar.success("已开启", "程序启动时将自动运行勾选的配置",
                            parent=self, duration=1500)
        else:
            InfoBar.info("已关闭", "程序启动时不会自动运行任何配置",
                         parent=self, duration=1500)

    def _on_autorun_item_changed(self, _item):
        names = []
        for i in range(self.autorun_list.count()):
            it = self.autorun_list.item(i)
            if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                if it.checkState() == Qt.CheckState.Checked:
                    names.append(it.text())
        self.settings.set('auto_run_configs', names)

    def _refresh_autorun_list(self):
        if not hasattr(self, 'autorun_list'):
            return
        lw = self.autorun_list
        lw.blockSignals(True)
        lw.clear()

        selected = set(self.settings.get('auto_run_configs', []) or [])
        names = sorted(self.cfg_mgr.all().keys())

        if not names:
            item = QListWidgetItem("（暂无配置，请先在主界面新建配置）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            lw.addItem(item)
        else:
            for name in names:
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if name in selected
                    else Qt.CheckState.Unchecked
                )
                lw.addItem(item)

        lw.blockSignals(False)
        lw.setEnabled(bool(self.settings.get('auto_run_enabled', False)))

    def _run_auto_configs_on_startup(self):
        if not self.settings.get('auto_run_enabled', False):
            return
        names = self.settings.get('auto_run_configs', []) or []
        if not names:
            return
        for name in names:
            if self.cfg_mgr.has(name):
                try:
                    self._on_cfg_run(name)
                except Exception as e:
                    print(f"[自启动配置失败] {name}: {e}")

    def _onboarding(self):
        default_hk = self.settings.get('hotkey', 'Ctrl+Alt+Q')
        dlg = OnboardingDialog(default_hk, self)
        dlg.exec()
        if not dlg.skipped():
            hk = dlg.hotkey()
            if hk:
                self.settings.set('hotkey', hk)
                ok = self._hotkey_filter.register(hk)
                if not ok:
                    InfoBar.warning(
                        "快捷键注册失败", f"{hk} 可能被占用，请到设置更换",
                        parent=self, duration=3000,
                    )
        self.settings.set('initialized', True)
        if hasattr(self, 'hotkey_recorder'):
            self.hotkey_recorder.set_hotkey(self.settings.get('hotkey', ''))
        self._update_hk_hint()

    def _close_all_videos(self):
        for k, w in list(self._playing.items()):
            try:
                w.close()
            except RuntimeError:
                pass
        self._playing.clear()
        QTimer.singleShot(0, self._refresh_all)

    def _on_hotkey_recorded(self, hk):
        if hk:
            ok = self._hotkey_filter.register(hk)
            if not ok:
                InfoBar.warning("快捷键注册失败", f"{hk} 可能被占用",
                                parent=self, duration=3000)
                old = self.settings.get('hotkey', '')
                self.hotkey_recorder.set_hotkey(old)
                if old:
                    self._hotkey_filter.register(old)
                return
        else:
            self._hotkey_filter.unregister()
        self.settings.set('hotkey', hk)
        self._update_hk_hint()
        InfoBar.success("快捷键已更新", hk if hk else "已清除",
                        parent=self, duration=1500)

    def _clear_hotkey(self):
        self.hotkey_recorder.set_hotkey("")

    def _update_hk_hint(self):
        hk = self.settings.get('hotkey', '')
        if hasattr(self, 'hk_hint'):
            self.hk_hint.setText(
                f"快捷键：{hk}  关闭所有视频窗口" if hk
                else "未设置快捷键（可在设置页配置）"
            )

    def _list_videos(self):
        if not os.path.isdir(self.video_dir):
            return []
        return sorted([
            n for n in os.listdir(self.video_dir)
            if n.lower().endswith(VIDEO_EXTS)
        ])

    def _get_playing(self, key):
        w = self._playing.get(key)
        if w is None:
            return None
        try:
            _ = w.config_name
            return w
        except RuntimeError:
            del self._playing[key]
            return None

    def _refresh_all(self):
        if self._refreshing:
            self._refresh_requested = True
            return
        self._refreshing = True
        try:
            self._refresh_cfg_list()
            self._refresh_vid_list()
            self._refresh_autorun_list()
        except Exception as e:
            print(f"[刷新列表失败] {e}")
            traceback.print_exc()
        finally:
            self._refreshing = False
            if self._refresh_requested:
                self._refresh_requested = False
                QTimer.singleShot(0, self._refresh_all)

    def _refresh_cfg_list(self):
        self.cfg_list.clear()
        for name, cfg in sorted(self.cfg_mgr.all().items()):
            playing = self._get_playing(f"cfg:{name}") is not None
            item = QListWidgetItem(); item.setSizeHint(QSize(0, 44))
            self.cfg_list.addItem(item)
            card = ConfigCard(name, cfg, playing, self.cfg_list)
            card.runClicked.connect(self._on_cfg_run)
            card.editClicked.connect(self._on_cfg_edit)
            card.deleteClicked.connect(self._on_cfg_delete)
            self.cfg_list.setItemWidget(item, card)

    def _refresh_vid_list(self):
        self.vid_list.clear()
        ref_count = {}
        for cfg in self.cfg_mgr.all().values():
            v = cfg.get('video', '')
            if v:
                ref_count[v] = ref_count.get(v, 0) + 1
        for name in self._list_videos():
            playing = self._get_playing(f"vid:{name}") is not None
            item = QListWidgetItem(); item.setSizeHint(QSize(0, 44))
            self.vid_list.addItem(item)
            card = VideoCard(name, playing, ref_count.get(name, 0), self.vid_list)
            card.runClicked.connect(self._on_vid_run)
            self.vid_list.setItemWidget(item, card)

    def _on_import(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v);;所有文件 (*.*)"
        )
        if not files:
            return
        video_abs = os.path.abspath(self.video_dir)
        imported = 0
        for src in files:
            if os.path.dirname(os.path.abspath(src)) == video_abs:
                continue
            name = os.path.basename(src)
            dst = os.path.join(self.video_dir, name)
            if os.path.exists(dst):
                base, ext = os.path.splitext(name)
                i = 1
                while os.path.exists(dst):
                    dst = os.path.join(self.video_dir, f"{base}_{i}{ext}")
                    i += 1
            try:
                shutil.copy2(src, dst)
                imported += 1
            except Exception as e:
                print(f"[导入失败] {src}: {e}")
        if imported:
            InfoBar.success("导入成功", f"已导入 {imported} 个视频到 video/",
                            parent=self, duration=2000)
            self._refresh_all()

    def _on_new_config(self):
        videos = self._list_videos()
        if not videos:
            InfoBar.warning("暂无视频", "请先导入视频", parent=self, duration=2000)
            return
        idx = 1
        while self.cfg_mgr.has(f"配置{idx}"):
            idx += 1
        name = f"配置{idx}"
        cfg = default_config(videos[0])

        def _save(cfg_data):
            return self.cfg_mgr.set(name, cfg_data)

        dlg = ConfigDialog(name, videos[0], cfg, videos,
                           save_callback=_save, parent=self)
        dlg.exec()

        if dlg.was_saved():
            QTimer.singleShot(0, self._refresh_all)

    def _on_cfg_edit(self, name):
        cfg = self.cfg_mgr.get(name)
        if not cfg:
            InfoBar.warning("配置不存在", name, parent=self, duration=2000)
            return

        def _save(cfg_data):
            cfg_data['layer'] = cfg.get('layer', 0)
            return self.cfg_mgr.set(name, cfg_data)

        dlg = ConfigDialog(name, cfg.get('video', ''), cfg,
                           self._list_videos(),
                           save_callback=_save, parent=self)
        dlg.exec()

        if dlg.was_saved():
            QTimer.singleShot(0, self._refresh_all)

    def _on_cfg_delete(self, name):
        if self._get_playing(f"cfg:{name}") is not None:
            InfoBar.warning("无法删除", "该配置正在播放中，请先关闭",
                            parent=self, duration=2000)
            return
        self.cfg_mgr.delete(name)
        names = self.settings.get('auto_run_configs', []) or []
        if name in names:
            names = [n for n in names if n != name]
            self.settings.set('auto_run_configs', names)
        self._refresh_all()

    def _on_cfg_run(self, name):
        key = f"cfg:{name}"
        w = self._get_playing(key)
        if w is not None:
            w.close()
            return
        cfg = self.cfg_mgr.get(name)
        if not cfg:
            return
        video = cfg.get('video', '')
        path = os.path.join(self.video_dir, video) if video else ''
        if not video or not os.path.exists(path):
            InfoBar.error("视频不存在", video or "(未指定)",
                          parent=self, duration=2500)
            return
        self._open_window(key, name, path, cfg, from_config=True)

    def _on_vid_run(self, name):
        key = f"vid:{name}"
        w = self._get_playing(key)
        if w is not None:
            w.close()
            return
        path = os.path.join(self.video_dir, name)
        if not os.path.exists(path):
            InfoBar.error("文件不存在", name, parent=self, duration=2500)
            return
        cfg = default_config(name, loop=True)
        self._open_window(key, name, path, cfg, from_config=False)

    def _open_window(self, key, title, video_path, cfg, from_config):
        w = VideoWindow(title, video_path, cfg)
        w.from_config = from_config
        w.closed.connect(self._on_window_closed)
        try:
            w.set_playback_options(
                fps_limit=int(self.settings.get('fps_limit', DEFAULT_FPS_LIMIT)),
                quality=str(self.settings.get('render_quality', DEFAULT_RENDER_QUALITY)),
                occlusion_stop_percent=int(self.settings.get(
                    'occlusion_stop_percent', DEFAULT_OCCLUSION_STOP_PERCENT)),
                occlusion_keep_audio=bool(self.settings.get(
                    'occlusion_keep_audio', DEFAULT_OCCLUSION_KEEP_AUDIO)),
            )
        except Exception:
            pass
        self._playing[key] = w
        w.show()
        self._refresh_all()

    def _on_window_closed(self, w):
        for k in [k for k, v in self._playing.items() if v is w]:
            del self._playing[k]
        if getattr(w, 'from_config', False) and self.cfg_mgr.has(w.config_name):
            try:
                self.cfg_mgr.set(w.config_name, w.snapshot_config())
            except Exception:
                pass
        QTimer.singleShot(0, self._refresh_all)


# ═══════════════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════════════
def main():
    try:
        ensure_autostart_command_current()

        app = QApplication(sys.argv)

        base_font = QFont()
        base_font.setFamily("Microsoft YaHei UI")
        base_font.setPointSize(9)
        app.setFont(base_font)

        # 主题系统就绪：在 QApplication 之后才能调用 setTheme
        THEME.mark_ready()

        # 读取用户保存的主题并立即应用（默认 auto = 跟随系统）
        saved_theme = "auto"
        try:
            _tmp_path = os.path.join(get_data_dir(), APP_SETTINGS_FILE)
            if os.path.exists(_tmp_path):
                with open(_tmp_path, 'r', encoding='utf-8') as f:
                    _d = json.load(f)
                if isinstance(_d, dict):
                    _v = str(_d.get('theme_mode', 'auto')).lower()
                    if _v in ("auto", "light", "dark"):
                        saved_theme = _v
        except Exception as e:
            print(f"[主题初始化读取失败] {e}")
        THEME.set_mode(saved_theme, force=True)

        window = MainWindow()

        autostart_mode = AUTOSTART_FLAG in sys.argv

        if autostart_mode:
            window.start_in_tray()
        else:
            window.show()
            try:
                screen = app.primaryScreen().availableGeometry()
                w = window.frameGeometry().width()
                h = window.frameGeometry().height()
                window.move(
                    screen.x() + (screen.width() - w) // 2,
                    screen.y() + (screen.height() - h) // 2,
                )
            except Exception as e:
                print(f"[居中失败] {e}")

        sys.exit(app.exec())
    except Exception:
        traceback.print_exc()
        input("按回车退出...")


if __name__ == "__main__":
    main()