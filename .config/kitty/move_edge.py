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

Requires kitty 0.50.0 or later.

CONFIGURATION

Add key mappings to your `kitty.conf`:

  map ctrl+shift+left  kitten move_edge.py left
  map ctrl+shift+right kitten move_edge.py right 3    # cells, default 1
"""

from kittens.tui.handler import result_handler
from kitty.boss import Boss
from kitty.fast_data_types import get_options, ring_bell
from kitty.layout.splits import Splits

# direction: (edges to try in order, sign of the movement)
DIRECTIONS = {
    'left':  (('right', 'left'), -1),
    'right': (('right', 'left'), +1),
    'up':    (('bottom', 'top'), -1),
    'down':  (('bottom', 'top'), +1),
}

# Required by kitty's kitten loader; never called because of no_ui=True
def main(args: list[str]) -> None:
    pass

@result_handler(no_ui=True)
def handle_result(args: list[str], answer: None, target_window_id: int, boss: Boss) -> None:
    edges, sign = DIRECTIONS[args[1]]
    cells = int(args[2]) if len(args) > 2 else 1

    window = boss.window_id_map.get(target_window_id)
    tab = window.tabref() if window else None
    if tab is None or not isinstance(tab.current_layout, Splits):
        return

    layout = tab.current_layout
    for edge in edges:
        # Outer edges of the tab have no separator
        if layout.pair_for_window_edge(tab.windows, window.id, edge) is not None:
            if layout.modify_size_of_window_edge(tab.windows, window.id, edge, sign * cells):
                tab.relayout()
                return
            break

    # Same feedback as resize_window when nothing can move
    if get_options().enable_audio_bell:
        ring_bell(tab.os_window_id)
