from typing import Any, Dict

from kitty.boss import Boss
from kitty.window import Window

def on_focus_change(boss: Boss, window: Window, data: Dict[str, Any])-> None:
    if data['focused']:
        boss.call_remote_control(window, (
            'set-colors',
            f'--match=id:{window.id}',
            '~/.config/kitty/theme-broadcast.conf'
        ))
    else:
        boss.call_remote_control(window, (
            'set-colors',
            f'--match=id:{window.id}',
            '--reset'
        ))

def on_close(boss: Boss, window: Window, data: Dict[str, Any])-> None:
    on_focus_change(boss, window, { 'focused': False })