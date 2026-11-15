"""
Toggle window title bars

Switch window_title_bar_min_windows to 1 (always show title bars), and back to
the value it had before, for all tabs of all OS windows. Unlike the built-in
toggle_window_title_bars action, the bars stay visible after dragging a window.

If the value is already 1, the toggle switches between 1 and 0 (never show).

COMPATIBILITY

Requires kitty 0.50.0 or later, for window title bars.

INSTALLATION

Put this file in your kitty config directory.

CONFIGURATION

Add a key mapping to your `kitty.conf`:

  map ctrl+shift+f3 kitten window_title_bars.py

Reloading the config resets the toggle to the value from kitty.conf.
"""

from kittens.tui.handler import result_handler
from kitty.boss import Boss
from kitty.fast_data_types import get_options

# The value to restore is kept on the options object itself, so that it is
# discarded along with the toggled value when the config is reloaded
SAVED = '_window_title_bars_saved_min_windows'

# Required by kitty's kitten loader; never called because of no_ui=True
def main(args: list[str]) -> None:
    pass

@result_handler(no_ui=True)
def handle_result(args: list[str], answer: None, target_window_id: int, boss: Boss) -> None:
    opts = get_options()
    saved = getattr(opts, SAVED, None)
    if saved is None:
        current = opts.window_title_bar_min_windows
        setattr(opts, SAVED, current)
        opts.window_title_bar_min_windows = 0 if current == 1 else 1
    else:
        opts.window_title_bar_min_windows = saved
        setattr(opts, SAVED, None)

    # The option is read when laying out a tab, so relayout all of them
    for tm in boss.all_tab_managers:
        for tab in tm:
            tab.relayout()
