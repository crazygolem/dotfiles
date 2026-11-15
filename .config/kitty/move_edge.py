"""
Diegetic window resize

Resize a split by moving the separator in the direction of the arrow, instead of
making the window wider/narrower/taller/shorter. Splits layout only.

When the window has a separator on both sides (e.g. the middle of three
columns), the right/bottom one moves, as in tmux, so opposite directions always
undo each other.

When there is no separator on the right/bottom, i.e. the window is at the edge
of the tab, the left/top one is moved instead, still in the arrow's direction.

COMPATIBILITY

Requires kitty 0.50.0 or later, for the `resize-window-edge` remote control
command.

INSTALLATION

Put this file in your kitty config directory.

Remote control doesn't need to be enabled in kitty.conf (`allow_remote_control`):
the kitten runs inside kitty and calls the remote control command directly.

CONFIGURATION

Add key mappings to your `kitty.conf`:

  map ctrl+shift+left  kitten move_edge.py left
  map ctrl+shift+right kitten move_edge.py right 3    # cells, default 1
"""

import json
from typing import Any

from kittens.tui.handler import result_handler
from kitty.boss import Boss
from kitty.fast_data_types import get_options, ring_bell
from kitty.window import Window

# direction: (preferred edge, fallback edge, sign of the movement)
DIRECTIONS = {
    'left':  ('right', 'left', -1),
    'right': ('right', 'left', +1),
    'up':    ('bottom', 'top', -1),
    'down':  ('bottom', 'top', +1),
}

# Required by kitty's kitten loader; never called because of no_ui=True
def main(args: list[str]) -> None:
    pass

@result_handler(no_ui=True)
def handle_result(args: list[str], answer: None, target_window_id: int, boss: Boss) -> None:
    preferred, fallback, sign = DIRECTIONS[args[1]]
    cells = int(args[2]) if len(args) > 2 else 1

    window = boss.window_id_map.get(target_window_id)
    if window is None:
        return

    reply = move_edge(boss, window, preferred, sign * cells)
    if preferred not in reply['edges'] and fallback in reply['edges']:
        reply = move_edge(boss, window, fallback, sign * cells)

    # Same feedback as resize_window when nothing can move
    if reply['failed'] and get_options().enable_audio_bell:
        ring_bell(window.os_window_id)

def move_edge(boss: Boss, window: Window, edge: str, increment: int) -> dict[str, Any]:
    # The reply lists the window's internal edges (outer edges of the tab have
    # no separator), and `failed` is set when nothing moved: outer edge, edge at
    # its size limit, or a layout other than Splits
    reply = boss.call_remote_control(window, (
        'resize-window-edge', '--self', f'--edge={edge}', f'--increment={increment}',
    ))
    return json.loads(reply)
