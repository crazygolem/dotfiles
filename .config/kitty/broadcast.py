"""
Broadcast from a dock

Wrapper for the `broadcast` kitten that uses a window docked at the top of the
current tab to broadcast from, and only broadcasts to visible windows in that
tab. The input is hidden in the dock, as the typed text is visible in the
target windows anyway.

By default, the list of broadcast targets is fixed when the broadcast starts.
But the wrapper can be called again from another window of the tab to
"refresh" it. Calling it from the broadcast dock ends the broadcast instead.

With the `--follow` option, the targets follow the windows of the tab instead:
windows that were opened (including overlays), closed, or moved to or from the
tab are added or removed when the dock gets the focus. You can only type in the
dock while it has the focus, and almost every way of changing the windows takes
the focus away from it. Changes made while the dock keeps the focus, such as a
window opened in the background or an overlay closing by itself, are picked up
the next time it gets the focus, or right away when this file is also loaded as
a global watcher (see CONFIGURATION).

LIMITATIONS

The broadcast window can't contain messages such as the broadcast status or
instructions. The initial message disappears as soon as you start typing
something, leaving the window empty.

The broadcast theme's tab bar colors (e.g. the active tab's or the tab bar
margin's) apply to all OS windows of the same kitty process (e.g. new OS windows
created with the ctrl+shift+n shortcut). The cursor's colors are set for each
broadcast target window, so the cursor colors can be used to identify broadcast
targets while the broadcast dock has the focus.

COMPATIBILITY

Requires kitty 0.50.0 or later, for docked windows.

kitty's internals aren't stable, so this file goes through remote control
commands as much as possible. The few internals without an equivalent are
wrapped in the functions of the KITTY INTERNALS section at the end, the place to
look if something breaks with a future version of kitty: the user variables and
keyboard mode of a window, the broadcast session of the kitten (for the follow
mode), timers, error messages and the config directory.

INSTALLATION

You need the following files in your kitty config directory:
- broadcast.py (this file): The wrapper, as well as the watchers that apply the
  theme to the broadcast dock and handle the follow mode.
- theme-broadcast.conf: The theme to apply when broadcasting. Its `cursor` and
  `cursor_text_color` settings also apply to the cursor of the target windows.

Remote control doesn't need to be enabled in kitty.conf (`allow_remote_control`):
the kitten and the watchers run inside kitty and call remote control commands
directly.

CONFIGURATION

Add a key mapping to your `kitty.conf`:

  map f4 kitten broadcast.py

You can then hit F4 on your keyboard in a window to open a broadcast dock at
the top of its tab. Hit F4 again or Ctrl+Esc in the dock to end the broadcast.

To make the targets follow the windows of the tab, add the `--follow` option:

  map f4 kitten broadcast.py --follow

Optionally, for the follow mode, also load this file as a global watcher, so
that the targets are updated right away, even while the dock keeps the focus.
Restart kitty after adding it (see the WATCHERS section):

  watcher broadcast.py
"""

import json
import os
import re
import secrets
import sys
from time import monotonic
from typing import Any, Callable, Iterable

from kittens.tui.handler import result_handler
from kitty.boss import Boss
from kitty.window import Window

# The theme to apply to the broadcast dock while it has the focus, in the kitty
# config directory.
#
# Note: `set-colors` only expands `~` in color file paths, a relative path would
# be resolved with respect to kitty's working directory, not the config
# directory.
THEME_FILE = 'theme-broadcast.conf'

# The settings of the theme that are also applied to the target windows, whose
# cursor kitty shows while the dock has the focus.
CURSOR_SETTINGS = ('cursor', 'cursor_text_color')

# The keys that toggle hiding the input and end the session in the broadcast
# kitten. They are passed to the kitten explicitly, so that pressing them for
# the user doesn't depend on the built-in broadcast kitten's defaults (in case
# they ever change; these are the current defaults).
HIDE_INPUT_TOGGLE = 'Ctrl+Alt+Esc'
END_SESSION = 'Ctrl+Esc'

# User variables:
# - BROADCASTING_VAR, on the broadcast dock: the match expression of its
#   targets. It also marks the window as a broadcasting window.
# - FOLLOW_VAR, on the broadcast dock with --follow: a token identifying the
#   broadcast.
# - TARGET_VAR, on the target windows with --follow: the token of the broadcast
#   they are a target of.
BROADCASTING_VAR = 'broadcast_to'
FOLLOW_VAR = 'broadcast_follow'
TARGET_VAR = 'broadcast_target'

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

# KITTEN #######################################################################

# Required by kitty's kitten loader; never called because of no_ui=True
def main(args: list[str]) -> None:
    pass

# The target window is the one the mapping was triggered in: the active window
# of the active tab, or the broadcast dock when it has the focus.
@result_handler(no_ui=True)
def handle_result(args: list[str], answer: None, target_window_id: int, boss: Boss) -> None:
    options = args[1:]
    if unknown := [a for a in options if a != '--follow']:
        show_error(boss, 'broadcast.py: unknown arguments', ' '.join(unknown))
        return
    follow = '--follow' in options

    window = boss.window_id_map.get(target_window_id)
    os_windows = list_os_windows(boss)
    tab = next((t for t in tabs_of(os_windows) if target_window_id in window_ids_of(t)), None)
    if window is None or tab is None:
        return

    # The broadcasting windows in the tab. Normally just the broadcast dock if
    # there is one. The windows of a tab include the docks.
    broadcasters = [w['id'] for w in tab['windows'] if is_broadcasting(w['user_vars'])]

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
    if target_window_id in broadcasters:
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
    #
    # With --follow, the targets are the windows that have TARGET_VAR set to the
    # token of this broadcast, which the watcher keeps up to date. The kitten
    # sends its match expression with every key, and kitty evaluates it every
    # time, so changes to the targets take effect without restarting it.
    follow_vars: tuple[str, ...] = ()
    if follow:
        token = secrets.token_hex(8)
        sync_targets(boss, os_windows, [(tab, token, None)])
        target_match = f'var:^{TARGET_VAR}$=^{token}$'
        follow_vars = (f'--var={FOLLOW_VAR}={token}',)
    else:
        target_match = match_ids(visible_targets(tab))

    dock_id = boss.call_remote_control(window, (
        'launch',
        f'--match=window_id:{target_window_id}',
        '--type=tab-dock', '--dock-edge=top', f'--dock-size={DOCK_SIZE}',
        '--window-title=Broadcast',
        '--allow-remote-control',
        f'--var={BROADCASTING_VAR}={target_match or "none"}',
        *follow_vars,
        '--watcher=broadcast.py',
        'kitty', '+kitten', 'broadcast',
        f'--hide-input-toggle={HIDE_INPUT_TOGGLE}',
        f'--end-session={END_SESSION}',
        f'--match={target_match or "id:0 and not id:0"}',
    ))
    hide_input_once_started(boss, int(dock_id))

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
        if not has_started(boss, dock):
            if monotonic() < deadline:
                return False
            print(f"broadcast.py: the kitten in window {dock_id} didn't start, not hiding the input", file=sys.stderr)
            return True

        boss.call_remote_control(dock, ('send-key', f'--match=id:{dock_id}', HIDE_INPUT_TOGGLE))

        # As soon as something is typed into the broadcast window, it scrolls
        # down again and hides the message, even when inputs are hidden. But at
        # least it opens showing something, making the window recognizable.
        boss.call_remote_control(dock, ('scroll-window', f'--match=id:{dock_id}', 'start'))
        return True

    call_repeatedly(step, POLL_INTERVAL)

def has_started(boss: Boss, dock: Window) -> bool:
    text = boss.call_remote_control(dock, ('get-text', f'--match=id:{dock.id}', '--extent=all'))
    return uses_kitty_keyboard_protocol(dock) and text.strip() != ''

# WINDOWS ######################################################################
#
# The windows are read from the output of `kitten @ ls`: a list of OS windows,
# with their tabs, and the windows and groups of the tabs, as JSON.

def list_os_windows(boss: Boss) -> list[dict[str, Any]]:
    return json.loads(boss.call_remote_control(None, ('ls',)))

def tabs_of(os_windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for o in os_windows for t in o['tabs']]

def window_ids_of(tab: dict[str, Any]) -> list[int]:
    return [w['id'] for w in tab['windows']]

def is_broadcasting(user_vars: dict[str, str]) -> bool:
    return BROADCASTING_VAR in user_vars

def match_ids(window_ids: Iterable[int]) -> str:
    return ' or '.join(f'id:{i}' for i in window_ids)

# The window ids of a match expression made by match_ids.
def ids_in_match(match: str) -> set[int]:
    return {int(i) for i in re.findall(r'\bid:(\d+)', match)}

# The visible windows in the tab: the top window of every group, except for
# docks (the broadcast dock, but also status bars, file trees, etc.) and
# broadcasting windows. The window the mapping was triggered in is included, as
# the dock doesn't cover it.
#
# Note: the groups of a tab include the docks, which are the groups with a
# `dock` key.
def visible_targets(tab: dict[str, Any]) -> list[int]:
    user_vars = {w['id']: w['user_vars'] for w in tab['windows']}
    return [
        g['windows'][-1] for g in tab['groups']
            if 'dock' not in g and g['windows']
            and not is_broadcasting(user_vars.get(g['windows'][-1], {}))
    ]

# The window that has the keyboard focus, if kitty has it: the active window of
# the active tab of the focused OS window.
def focused_window(os_windows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for o in os_windows:
        if o['is_focused']:
            for t in o['tabs']:
                if t['is_active']:
                    return next((w for w in t['windows'] if w['is_active']), None)
    return None

# The targets of a broadcast dock that still exist: the windows with its token
# with --follow, or the windows of its match expression otherwise.
def current_targets(os_windows: list[dict[str, Any]], dock_user_vars: dict[str, str]) -> list[int]:
    windows = [w for t in tabs_of(os_windows) for w in t['windows']]
    if token := dock_user_vars.get(FOLLOW_VAR):
        return [w['id'] for w in windows if w['user_vars'].get(TARGET_VAR) == token]
    ids = ids_in_match(dock_user_vars.get(BROADCASTING_VAR, ''))
    return [w['id'] for w in windows if w['id'] in ids]

def set_user_var(boss: Boss, window_ids: Iterable[int], name: str, value: str | None) -> None:
    var = name if value is None else f'{name}={value}'
    boss.call_remote_control(None, ('set-user-vars', f'--match={match_ids(window_ids)}', var))

# Set TARGET_VAR to the token of each broadcast on the visible windows of its
# tab, and unset it on the other windows that have it, wherever they are (e.g.
# moved to another tab, or covered by an overlay). Also update the broadcast
# session of the docks (see sync_broadcast_session).
#
# `owners` has the tab, token and dock id (None before the dock is launched) of
# each broadcast. They are all updated together from the same `os_windows`, so
# that a window moved from the tab of one to the tab of another ends up with
# the right token.
def sync_targets(
    boss: Boss, os_windows: list[dict[str, Any]], owners: list[tuple[dict[str, Any], str, int | None]],
) -> None:
    docks = {token: dock_id for _, token, dock_id in owners}
    current = {
        w['id']: w['user_vars'][TARGET_VAR] for t in tabs_of(os_windows) for w in t['windows']
            if w['user_vars'].get(TARGET_VAR) in docks
    }
    wanted = {wid: token for tab, token, _ in owners for wid in visible_targets(tab)}

    if unset := [wid for wid in current if wid not in wanted]:
        set_user_var(boss, unset, TARGET_VAR, None)
    for token, dock_id in docks.items():
        targets = {wid for wid, t in wanted.items() if t == token}
        if new := [wid for wid in targets if current.get(wid) != token]:
            set_user_var(boss, new, TARGET_VAR, token)
        if dock_id is not None:
            sync_broadcast_session(boss, dock_id, targets)

# The newest broadcast dock with --follow of each tab owns its targets. An
# older one is only still there while closing, after being replaced by a new
# dock.
def refresh_followed_targets(boss: Boss) -> None:
    os_windows = list_os_windows(boss)
    owners = []
    for tab in tabs_of(os_windows):
        docks = [(w['id'], w['user_vars'][FOLLOW_VAR]) for w in tab['windows'] if FOLLOW_VAR in w['user_vars']]
        if docks:
            dock_id, token = max(docks)
            owners.append((tab, token, dock_id))
    if owners:
        sync_targets(boss, os_windows, owners)

# WATCHERS #####################################################################
#
# The broadcast dock is launched with this file as its watcher.
#
# kitty only looks for the `on_*` functions when loading a watcher, and only for
# `main` and `handle_result` when loading a kitten, so each ignores the other's
# functions.
#
# This file can also be loaded as a global watcher (`watcher` in kitty.conf),
# for on_tab_bar_dirty, which kitty only calls for global watchers. The other
# functions then get the events of all windows, so they check that the window
# is a broadcast dock. With the same path (`broadcast.py`), kitty loads the file
# only once for both, and the functions aren't called twice for the dock.
#
# Note: the kitten is loaded again every time it runs, but a watcher is loaded
# once and kept until kitty quits, even when the config is reloaded. Changes to
# the functions below only take effect after restarting kitty.

# The ids of the broadcast docks with --follow, so that on_tab_bar_dirty can
# skip its many events while there is none. A dock is added when it gets the
# focus, which it does when it is launched.
following_docks: set[int] = set()

def on_focus_change(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    user_vars = window_user_vars(window)
    if not is_broadcasting(user_vars):
        return

    if data['focused']:
        boss.call_remote_control(window, (
            'set-colors', f'--match=id:{window.id}', config_path(THEME_FILE),
        ))
        # With --follow, catch up with the windows opened, closed or moved
        # while the dock didn't have the focus
        if FOLLOW_VAR in user_vars:
            following_docks.add(window.id)
            refresh_followed_targets(boss)
        color_target_cursors(boss, list_os_windows(boss), user_vars)
        return

    reset_theme(boss, window.id)

# kitty calls on_close after forgetting the window (`boss.window_id_map`), but
# before removing it from its tab. Until then, remote control commands with a
# match expression fail, as kitty can't look up all the windows of the tabs. So
# the clean up is done in the next tick of the event loop.
def on_close(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    user_vars = window_user_vars(window)
    if not is_broadcasting(user_vars):
        return
    following_docks.discard(window.id)

    def clean_up() -> None:
        # Clean up the targets of a broadcast with --follow
        if token := user_vars.get(FOLLOW_VAR):
            targets = [
                w['id'] for t in tabs_of(list_os_windows(boss)) for w in t['windows']
                    if w['user_vars'].get(TARGET_VAR) == token
            ]
            if targets:
                set_user_var(boss, targets, TARGET_VAR, None)

        reset_theme(boss, window.id)

    call_soon(clean_up)

# `set-colors --reset` resets all windows and the tab bars, not just the dock,
# which includes the cursor of the targets. Skip it when another broadcasting
# window has the focus, e.g. the dock replacing this one when the broadcast is
# refreshed, as this dock can lose the focus or close after that one applied
# the theme.
def reset_theme(boss: Boss, dock_id: int) -> None:
    focused = focused_window(list_os_windows(boss))
    if focused is not None and focused['id'] != dock_id and is_broadcasting(focused['user_vars']):
        return

    boss.call_remote_control(None, ('set-colors', '--reset'))

# Only called when this file is loaded as a global watcher.
#
# kitty marks the tab bar dirty right after adding or removing a window (and for
# many other reasons, e.g. title changes). Refresh the targets of the
# broadcasts with --follow in the next tick of the event loop, once for all the
# events of the current one, so that kitty is done updating the tab and layout.
refresh_scheduled = False

def on_tab_bar_dirty(boss: Boss, window: Window, data: dict[str, Any]) -> None:
    global refresh_scheduled
    if refresh_scheduled or not following_docks:
        return

    # The refresh is still marked as scheduled while it runs, as `set-colors`
    # marks the tab bars dirty too, which would schedule another refresh after
    # each one.
    def refresh() -> None:
        global refresh_scheduled
        try:
            refresh_followed_targets(boss)
            # Also color the cursor of new targets, if their dock has the focus
            os_windows = list_os_windows(boss)
            focused = focused_window(os_windows)
            if focused is not None and FOLLOW_VAR in focused['user_vars']:
                color_target_cursors(boss, os_windows, focused['user_vars'])
        finally:
            refresh_scheduled = False

    refresh_scheduled = True
    call_soon(refresh)

# Apply the cursor settings of the theme to the targets of the dock. Like the
# rest of the theme, they are reset when the dock loses the focus.
#
# A window that stops being a target while the dock keeps the focus keeps them
# until then. But it doesn't show its cursor anymore (see
# sync_broadcast_session) until it gets the focus, which the dock loses.
def color_target_cursors(boss: Boss, os_windows: list[dict[str, Any]], dock_user_vars: dict[str, str]) -> None:
    settings = theme_cursor_settings()
    targets = current_targets(os_windows, dock_user_vars)
    if settings and targets:
        boss.call_remote_control(None, ('set-colors', f'--match={match_ids(targets)}', *settings))

# The CURSOR_SETTINGS of the theme file, as `set-colors` arguments.
def theme_cursor_settings() -> list[str]:
    settings = []
    with open(config_path(THEME_FILE)) as f:
        for line in f:
            parts = line.split(maxsplit=1)
            if len(parts) == 2 and parts[0] in CURSOR_SETTINGS:
                settings.append(f'{parts[0]}={parts[1].strip()}')
    return settings

# KITTY INTERNALS ##############################################################
#
# Everything that isn't done with remote control commands or the documented
# kitten and watcher APIs is wrapped here, as kitty's internals aren't stable.
# If something breaks with a new version of kitty, look here first.

from kitty.constants import config_dir
from kitty.fast_data_types import add_timer, remove_timer
from kitty.rc.send_text import FocusChangedSession, sessions_map

# The path of a file in the kitty config directory.
def config_path(name: str) -> str:
    return os.path.join(config_dir, name)

# The user variables of a window passed to a watcher. `kitten @ ls` doesn't list
# a window that is closing, and this is cheaper for the many events of a global
# watcher.
def window_user_vars(window: Window) -> dict[str, str]:
    return window.user_vars

# Whether the program running in the window has enabled kitty's keyboard
# protocol.
def uses_kitty_keyboard_protocol(window: Window) -> bool:
    return window.screen.current_key_encoding_flags() != 0

# Make the broadcast session of the kitten in the dock contain exactly the
# targets, if the session has started.
#
# kitty uses the session to show the cursor of the targets while the dock has
# the focus, but only adds windows to it when the kitten starts and when it
# sends keys. So without this, a new target would only show its cursor after
# typing something in the dock, and a former target would keep showing it.
#
# The session id is generated by the kitten, but kitty registers an action with
# it on the dock when the session starts.
def sync_broadcast_session(boss: Boss, dock_id: int, target_ids: set[int]) -> None:
    dock = boss.window_id_map.get(dock_id)
    if dock is None:
        return
    sids = [a.sid for a in dock.actions_on_focus_change if isinstance(a, FocusChangedSession)]
    session = sessions_map.get(sids[0]) if sids else None
    if session is None:
        return

    for wid in session.window_ids ^ target_ids:
        if (w := boss.window_id_map.get(wid)) is not None:
            w.screen.render_unfocused_cursor = wid in target_ids and dock.is_focused
    session.window_ids.clear()
    session.window_ids.update(target_ids)

# Call `fn` in the next tick of kitty's event loop.
def call_soon(fn: Callable[[], None]) -> None:
    add_timer(lambda _: fn(), 0, False)

# Call `fn` every `interval` seconds until it returns True. It also stops when
# `fn` raises, so that the error isn't repeated every time.
def call_repeatedly(fn: Callable[[], bool], interval: float) -> None:
    def check(_: int | None) -> None:
        done = True
        try:
            done = fn()
        finally:
            if done:
                remove_timer(timer_id)

    timer_id = add_timer(check, interval, True)

# Show an error message to the user, in an overlay window.
def show_error(boss: Boss, title: str, message: str) -> None:
    boss.show_error(title, message)
