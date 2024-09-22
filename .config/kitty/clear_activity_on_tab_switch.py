from typing import Any, Dict

from kitty.boss import Boss
from kitty.window import Window

# Clears the 'activity_since_last_focus' flag in all windows of the active tab
# when switching to another tab. This makes the 'activity_symbol' appear only
# for new activity in the previously active tab.
def on_focus_change(boss: Boss, window: Window, data: Dict[str, Any])-> None:
    if data['focused']:
        return

    tm = boss.active_tab_manager
    if not tm:
        return

    tab = tm.tab_at_location('prev')
    if not tab or window.tab_id != tab.id:
        return

    for win in tab:
        if win.has_activity_since_last_focus:
            # It appears calling this method does not trigger an on_focus_change
            # on the target window.
            win.screen.focus_changed(True)
