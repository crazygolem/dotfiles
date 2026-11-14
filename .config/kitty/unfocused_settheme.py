import os
import weakref
from typing import Any, Dict

from kitty.boss import Boss
from kitty.colors import parse_colors
from kitty.constants import config_dir
from kitty.fast_data_types import current_focused_os_window_id
from kitty.tabs import TabManager
from kitty.window import Window

# Applies the tab bar colors from theme-unfocused.conf to the tab bar of OS
# windows that don't have the focus.
#
# Only the colors kitty keeps per tab bar can be overridden: active_tab_*,
# inactive_tab_* and tab_bar_background. Others such as tab_bar_margin_color are
# global to all OS windows and are ignored.
#
# `set-colors` (e.g. the broadcast theme) also patches the tab bar colors, but
# globally. Colors changed this way while the unfocused ones are applied become
# the colors to restore on focus.

unfocused, _ = parse_colors([os.path.join(config_dir, 'theme-unfocused.conf')])
unfocused = {k: v for k, v in unfocused.items() if k in {
    'active_tab_foreground', 'active_tab_background', 'inactive_tab_foreground',
    'inactive_tab_background', 'tab_bar_background',
} and v is not None}

# Colors of a tab bar before the unfocused ones were applied, for the overridden
# keys. Only contains tab bars with the unfocused colors applied.
bases: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

def reconcile(tm: TabManager) -> None:
    tab_bar = tm.tab_bar
    current = {k: int(v) for k, v in tab_bar.current_colors.items()}

    base = bases.get(tab_bar)
    if base is not None:
        base.update((k, current[k]) for k in base if current[k] != unfocused[k])

    if tm.os_window_id != current_focused_os_window_id():
        bases.setdefault(tab_bar, {k: current[k] for k in unfocused})
        desired = current | unfocused
    else:
        bases.pop(tab_bar, None)
        desired = current | (base or {})

    # Always patching all colors, as kitty resets some of the tab bar's screen
    # colors to the configured ones for keys missing in the spec.
    if desired != current:
        tab_bar.patch_colors(desired)

# Called synchronously when kitty marks the tab bar dirty, which it does when
# the OS window gains or loses the focus (after updating the focus state), and
# after `set-colors`. The tab bar gets redrawn afterwards, so no need to mark it
# dirty.
def on_tab_bar_dirty(boss: Boss, window: Window, data: Dict[str, Any]) -> None:
    reconcile(data['tab_manager'])
