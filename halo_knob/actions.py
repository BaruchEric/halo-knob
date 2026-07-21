"""Output primitives: scroll, zoom, volume/media keys, keystrokes, mouse click.

Scroll & keyboard are CGEvents; volume/media are system-defined NSEvents (the only
way to drive the real volume HUD + media transport). Keyboard/mouse synthesis may
require Accessibility permission on top of Input Monitoring — see accessibility_trusted().
"""
import ctypes

from AppKit import NSEvent
from Quartz import (
    CGEventCreateScrollWheelEvent, CGEventPost, CGEventCreateKeyboardEvent, CGEventSetFlags,
    CGEventCreateMouseEvent, CGEventCreate, CGEventGetLocation,
    kCGHIDEventTap, kCGScrollEventUnitLine,
    kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGMouseButtonLeft,
    kCGEventFlagMaskCommand, kCGEventFlagMaskShift, kCGEventFlagMaskControl, kCGEventFlagMaskAlternate,
)

NS_SYSTEM_DEFINED = 14
NX_SUBTYPE_AUX = 8

# NX_KEYTYPE_* media key codes
MK_SOUND_UP, MK_SOUND_DOWN, MK_BRIGHT_UP, MK_BRIGHT_DOWN = 0, 1, 2, 3
MK_MUTE, MK_PLAY, MK_NEXT, MK_PREV = 7, 16, 17, 18

_MODS = {
    "cmd": kCGEventFlagMaskCommand, "command": kCGEventFlagMaskCommand, "⌘": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift, "⇧": kCGEventFlagMaskShift,
    "ctrl": kCGEventFlagMaskControl, "control": kCGEventFlagMaskControl, "⌃": kCGEventFlagMaskControl,
    "alt": kCGEventFlagMaskAlternate, "opt": kCGEventFlagMaskAlternate, "option": kCGEventFlagMaskAlternate,
    "⌥": kCGEventFlagMaskAlternate,
}

# US-ANSI virtual keycodes
_KEYS = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11,
    "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21,
    "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31,
    "u": 32, "[": 33, "i": 34, "p": 35, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "`": 50,
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51, "backspace": 51, "escape": 53,
    "esc": 53, "left": 123, "right": 124, "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}

_appservices = ctypes.CDLL(
    "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
_appservices.AXIsProcessTrusted.restype = ctypes.c_bool


def accessibility_trusted() -> bool:
    return bool(_appservices.AXIsProcessTrusted())


def parse_combo(spec: str):
    """'cmd+shift+p' -> (keycode, flags). Raises ValueError on unknown key."""
    parts = [p.strip().lower() for p in spec.replace(" ", "").split("+") if p.strip()]
    flags = 0
    key = None
    for p in parts:
        if p in _MODS:
            flags |= _MODS[p]
        else:
            key = p
    if key is None or key not in _KEYS:
        raise ValueError(f"unknown key in combo: {spec!r}")
    return _KEYS[key], flags


def scroll(lines: int):
    """Vertical scroll. Positive = up."""
    ev = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, int(lines))
    CGEventPost(kCGHIDEventTap, ev)


def hscroll(lines: int):
    """Horizontal scroll. Positive = right."""
    ev = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 2, 0, int(lines))
    CGEventPost(kCGHIDEventTap, ev)


def keystroke(keycode: int, flags: int = 0):
    for down in (True, False):
        ev = CGEventCreateKeyboardEvent(None, keycode, down)
        if flags:
            CGEventSetFlags(ev, flags)
        CGEventPost(kCGHIDEventTap, ev)


def combo(spec: str):
    keycode, flags = parse_combo(spec)
    keystroke(keycode, flags)


def media_key(key: int):
    for down in (True, False):
        flags = 0xA00 if down else 0xB00
        data1 = (key << 16) | ((0xA if down else 0xB) << 8)
        ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            NS_SYSTEM_DEFINED, (0, 0), flags, 0, 0, None, NX_SUBTYPE_AUX, data1, -1)
        cg = ev.CGEvent()
        if cg is not None:
            CGEventPost(kCGHIDEventTap, cg)


def mouse_click():
    loc = CGEventGetLocation(CGEventCreate(None))
    for etype in (kCGEventLeftMouseDown, kCGEventLeftMouseUp):
        ev = CGEventCreateMouseEvent(None, etype, loc, kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, ev)
