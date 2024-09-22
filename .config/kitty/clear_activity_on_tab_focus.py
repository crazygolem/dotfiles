from typing import Any, Dict

from kitty.boss import Boss
from kitty.window import Window

# Clears the 'activity_since_last_focus' flag in all windows of the active tab
# such that switching to a tab that has the 'activity_symbol' and back to
# another tab removes the 'activity_symbol' from the tab's title.
def on_focus_change(boss: Boss, window: Window, data: Dict[str, Any])-> None:
    if not data['focused']:
        return

    tm = boss.active_tab_manager
    if tm is None:
        return

    for win in tm.active_tab:
        if win.has_activity_since_last_focus:
            # It appears calling this method does not trigger an on_focus_change
            # on the target window.
            win.screen.focus_changed(True)
