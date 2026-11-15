"""
Broadcast from a dock

Wrapper for the `broadcast` kitten that uses a window docked at the top of the
current tab to broadcast from, and only broadcasts to visible windows in that
tab. The input is hidden in the dock, as the typed text is visible in the
target windows anyway.

The list of broadcast targets is not updated when new windows (including
overlays) are created, as it doesn't seem currently possible to react to such
events. But the wrapper can be called again from another window of the tab to
"refresh" it. Calling it from the broadcast dock ends the broadcast instead.

COMPATIBILITY

Requires kitty 0.50.0 or later, for docked windows. Mapped kittens can use
remote control commands without `allow_remote_control`.

INSTALLATION

You need the following files in your kitty config directory:
- broadcast.py (this file): The wrapper, which is also the watcher that applies
  the theme to the broadcast dock.
- theme-broadcast.conf: The theme to apply when broadcasting.

LIMITATIONS

The broadcast window can't contain messages such as the broadcast status or
instructions. The initial message disappears as soon as you start typing
something, leaving the window empty.

CONFIGURATION

Add a key mapping to your `kitty.conf`:

  map f4 kitten broadcast.py

You can then hit F4 on your keyboard in a window to open a broadcast dock at
the top of its tab. Hit F4 again or Ctrl+Esc in the dock to end the broadcast.
"""

import os
from time import monotonic
from typing import Any, Iterable

from kittens.tui.handler import result_handler
from kitty.boss import Boss
from kitty.constants import config_dir
from kitty.fast_data_types import add_timer, remove_timer
from kitty.utils import log_error
from kitty.window import Window

# The theme to apply to the broadcast dock while it has the focus.
#
# Note: `set-colors` only expands `~` in color file paths, a relative path would
# be resolved with respect to kitty's working directory, not the config
# directory.
THEME = os.path.join(config_dir, 'theme-broadcast.conf')

# The keys that toggle hiding the input and end the session in the broadcast
# kitten. They are passed to the kitten explicitly, so that pressing them for
# the user doesn't depend on the built-in broadcast kitten's defaults (in case
# they ever change; these are the current defaults).
HIDE_INPUT_TOGGLE = 'Ctrl+Alt+Esc'
END_SESSION = 'Ctrl+Esc'

# Height of the broadcast dock as a number of rows, or as a percentage of the
# tab with a `%` suffix.
#
# Hiding the input makes the kitten print a newline, "Input hidden, press
# Ctrl+Alt+Esc to unhide:" and another newline below its header, and each Enter
# prints a newline. So with fewer than 5 rows the header scrolls out of view,
# and with 1 row the dock is blank.
DOCK_SIZE = 1

# How long to wait for the kitten in the dock to start, and how often to check,
# in seconds.
START_TIMEOUT = 2.0
POLL_INTERVAL = 0.02

# Required by kitty's kitten loader; never called because of no_ui=True
def main(args: list[str]) -> None:
    pass

# The target window is the one the mapping was triggered in: the active window
# of the active tab, or the broadcast dock when it has the focus.
@result_handler(no_ui=True)
def handle_result(args: list[str], answer: None, target_window_id: int, boss: Boss) -> None:
    window = boss.window_id_map.get(target_window_id)
    tab = window.tabref() if window is not None else None
    if window is None or tab is None:
        return

    # The broadcasting windows in the tab. Normally just the broadcast dock if
    # there is one. Iterating over the tab includes the docks.
    broadcasters = [w for w in tab if is_broadcasting(w)]

    # The visible windows in the tab: the top window of every group, except for
    # docks (the broadcast dock, but also status bars, file trees, etc.) and
    # broadcasting windows. The window the mapping was triggered in is
    # included, as the dock doesn't cover it.
    #
    # Note: `tab.windows.groups` only has the normal groups, the docks are kept
    # separately.
    targets = [
        g.windows[-1] for g in tab.windows.groups
            if g.windows and not is_broadcasting(g.windows[-1])
    ]

    # Starting the broadcast again when the tab already has a broadcast dock
    # should not add a new dock next to the existing one, but instead replace
    # it. The effect is that the broadcast continues, but the list of target
    # windows is refreshed to include windows that were opened since the last
    # broadcast launch.
    #
    # The old dock closes asynchronously, so it can briefly coexist with the new
    # one. Docks are never targets so it doesn't matter here, and the watcher
    # (see on_focus_change) takes care of the theme.
    #
    # When called from a broadcasting window, just end the broadcast. Without
    # the early return, it would depend on whether the window is already gone
    # when launching the new dock in its tab.
    if broadcasters:
        boss.call_remote_control(window, (
            'send-key', f'--match={match_ids(broadcasters)}', END_SESSION,
        ))
    if is_broadcasting(window):
        return

    # The broadcasting window created by the broadcast kitten gets always
    # excluded automatically.
    #
    # Note: an empty match expression is interpreted by kitty's matching routine
    # to mean `all`, and the same happens with an invalid match expression such
    # as 'none' (as opposed to a valid, non-empty match expression that matches
    # nothing).
    #
    # The tab bar displays the title of the active window, so the window title
    # is visible while the dock has the focus. It stands in for the kitten's
    # header, which doesn't stay visible in the dock (see DOCK_SIZE).
    target_match = match_ids(targets)
    dock_id = boss.call_remote_control(window, (
        'launch',
        f'--match=window_id:{window.id}',
        '--type=tab-dock', '--dock-edge=top', f'--dock-size={DOCK_SIZE}',
        '--window-title=Broadcast',
        '--allow-remote-control',
        f'--var=broadcast_to={target_match or "none"}',
        '--watcher=broadcast.py',
        'kitty', '+kitten', 'broadcast',
        f'--hide-input-toggle={HIDE_INPUT_TOGGLE}',
        f'--end-session={END_SESSION}',
        f'--match={target_match or "id:0 and not id:0"}',
    ))
    hide_input_once_started(boss, int(dock_id))

def is_broadcasting(window: Window | None) -> bool:
    return window is not None and 'broadcast_to' in window.user_vars

def match_ids(windows: Iterable[Window]) -> str:
    return ' or '.join(f'id:{w.id}' for w in windows)

# Hide the input by pressing the kitten's --hide-input-toggle key for the user.
#
# kitty encodes the key according to the keyboard mode of the dock, so it must
# only be sent once the kitten has enabled kitty's keyboard protocol. Otherwise
# it gets the legacy encoding, which the kitten doesn't recognize as the toggle
# and would broadcast. Also wait for the kitten to draw its header (in the
# scrollback, as the header scrolls out of view right away in a one-row dock),
# so that there is something to scroll back to.
#
# This runs inside kitty, so it polls with a timer instead of sleeping, which
# would block kitty's event loop, and with it the kitten's start.
def hide_input_once_started(boss: Boss, dock_id: int) -> None:
    deadline = monotonic() + START_TIMEOUT

    def step() -> bool:
        dock = boss.window_id_map.get(dock_id)
        if dock is None:
            # Closed before the kitten started
            return True
        if not has_started(dock):
            if monotonic() < deadline:
                return False
            log_error(f"broadcast.py: the kitten in window {dock_id} didn't start, not hiding the input")
            return True

        boss.call_remote_control(dock, ('send-key', f'--match=id:{dock_id}', HIDE_INPUT_TOGGLE))

        # As soon as something is typed into the broadcast window, it scrolls
        # down again and hides the message, even when inputs are hidden. But at
        # least it opens showing something, making the window recognizable.
        boss.call_remote_control(dock, ('scroll-window', f'--match=id:{dock_id}', 'start'))
        return True

    timer_id = 0

    def check(_: int | None) -> None:
        # Stop the repeating timer when done, and also when step() raises, so
        # that an error isn't repeated every POLL_INTERVAL
        done = True
        try:
            done = step()
        finally:
            if done:
                remove_timer(timer_id)

    timer_id = add_timer(check, POLL_INTERVAL, True)

def has_started(dock: Window) -> bool:
    return (
        dock.screen.current_key_encoding_flags() != 0
        and dock.as_text(add_history=True).strip() != ''
    )

# WATCHER ######################################################################
#
# The broadcast dock is launched with this file as its watcher. kitty only looks
# for the `on_*` functions when loading a watcher, and only for `main` and
# `handle_result` when loading a kitten, so each ignores the other's functions.
#
# Note: the kitten is loaded again every time it runs, but a watcher is loaded
# once and kept until kitty quits, even when the config is reloaded. Changes to
# the functions below only take effect after restarting kitty.

def on_focus_change(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    if data['focused']:
        boss.call_remote_control(window, (
            'set-colors', f'--match=id:{window.id}', THEME,
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
        'set-colors', f'--match=id:{window.id}', '--reset',
    ))

def on_close(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    on_focus_change(boss, window, {'focused': False})
