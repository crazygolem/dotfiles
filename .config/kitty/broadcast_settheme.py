from typing import Any, Dict, Optional

from kitty.boss import Boss
from kitty.window import Window

def is_broadcasting(window: Optional[Window]) -> bool:
    return window is not None and 'broadcast_to' in window.user_vars

def on_focus_change(boss: Boss, window: Window, data: Dict[str, Any])-> None:
    if data['focused']:
        boss.call_remote_control(window, (
            'set-colors',
            f'--match=id:{window.id}',
            '~/.config/kitty/theme-broadcast.conf'
        ))
        return

    # `set-colors --reset` resets all windows and the tab bars, not just this
    # window. Skip it when another broadcasting window has the focus, e.g. the
    # dock replacing this one when the broadcast is refreshed, as this window
    # can lose the focus or close after that one applied the theme.
    active = boss.active_window
    if active is not window and is_broadcasting(active):
        return

    boss.call_remote_control(window, (
        'set-colors',
        f'--match=id:{window.id}',
        '--reset'
    ))

def on_close(boss: Boss, window: Window, data: Dict[str, Any])-> None:
    on_focus_change(boss, window, { 'focused': False })
