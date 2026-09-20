"""Shared keyboard shortcut definitions and settings helpers."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QKeySequence


@dataclass(frozen=True)
class HotkeyDefinition:
    action_id: str
    label: str
    default_sequence: str


HOTKEY_DEFINITIONS = (
    HotkeyDefinition("previous_slide", "Previous Slide", "Up"),
    HotkeyDefinition("next_slide", "Next Slide", "Down"),
    HotkeyDefinition("previous_item", "Previous Schedule Item", "Left"),
    HotkeyDefinition("next_item", "Next Schedule Item", "Right"),
    HotkeyDefinition("media_toggle", "Play/Pause Media", "Space"),
    HotkeyDefinition("toggle_show_hide", "Show/Hide Output", "."),
    HotkeyDefinition("decrease_font", "Decrease Output Font", "-"),
    HotkeyDefinition("increase_font", "Increase Output Font", "+"),
    HotkeyDefinition("black_output", "Black Output", "Escape"),
    HotkeyDefinition("toggle_recording", "Start/Stop Recording", "R"),
    HotkeyDefinition("pause_recording", "Pause/Resume Recording", "P"),
    HotkeyDefinition("show_hotkeys", "Show Current Hotkeys", "?"),
)

DEFAULT_HOTKEYS = {
    definition.action_id: definition.default_sequence for definition in HOTKEY_DEFINITIONS
}


def normalize_hotkey(sequence: str) -> str:
    return QKeySequence(sequence).toString(QKeySequence.SequenceFormat.PortableText)


def configured_hotkeys(stored: object) -> dict[str, str]:
    hotkeys = DEFAULT_HOTKEYS.copy()
    if not isinstance(stored, dict):
        return hotkeys
    for action_id in hotkeys:
        sequence = stored.get(action_id)
        if isinstance(sequence, str) and normalize_hotkey(sequence):
            hotkeys[action_id] = normalize_hotkey(sequence)
    return hotkeys


def conflicting_action(
    hotkeys: dict[str, str], action_id: str, sequence: str
) -> str | None:
    normalized = normalize_hotkey(sequence)
    for other_action_id, other_sequence in hotkeys.items():
        if other_action_id != action_id and normalize_hotkey(other_sequence) == normalized:
            return other_action_id
    return None


def hotkey_label(action_id: str) -> str:
    return next(
        definition.label
        for definition in HOTKEY_DEFINITIONS
        if definition.action_id == action_id
    )
