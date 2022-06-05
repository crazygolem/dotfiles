--[[

Prevent the screen from blanking while a video is playing.

This script is a workaround for the GNOME+Wayland issue documented in the
[Disabling Screensaver] section of the mpv manual, and depends on
gnome-session-inhibit (usually provided by the gnome-session package) to set up
the inhibitors.


# CAVEATS

This is not (yet?) a foolproof solution.

At this time GNOME's implementation of the Inhibit protocol does not support the
SimluateUserActivity method:

    dbus-send --print-reply --session \
      --dest=org.gnome.ScreenSaver --type=method_call \
      /org/gnome/ScreenSaver org.gnome.ScreenSaver.SimulateUserActivity

So there seems to be no way to "poke" the system with a heartbeat to extend to
idle timeout for a bit and prevent blanking.

This means that inhibitors have to be installed, then removed when mpv exits.

The current implementation handles this via another application, which should
always be available on GNOME+Wayland desktops (because provided by gnome-session
itself): gnome-session-inhibit.

Executing gnome-session-inhibit to handle this is not ideal because if mpv does
not exit cleanly, gnome-session-inhibit is not necessarily killed (it can get
orphaned, and gets adopted by the init process), leaving the inhibitors intact
with no easy way for the user to figure it out.

Ideally this script should open a DBus session directly to handle the
inhibitors, as they would be removed if the DBus session gets disconnected (cf.
[Inhibit's documentation][Inhibit]):

> Applications should invoke [Inhibit ()] when they begin an operation that
> should not be interrupted [...] When the application completes the operation
> it should call Uninhibit() or disconnect from the session bus.

This is how [other applications] do it.

But really, the only secure way to handle this would be with a heartbeat to
regularly reset the idle timer, i.e. what SimulateUserActivity is supposed to
provide. Especially for a core security feature such as screen locking (cf.
xscreensaver author's [rant][jwz]).


# Work notes

## Detecting readiness

If remove_inhibitor is called too quickly after install_inhibitor, mpv sometimes
fails to remove the inhibitor. With the current implementation (where a single
"cookie" is used) it can lead to two inhibitors being installed at once, and the
first inhibitor only gets removed when closing mpv.

This cannot be reproduced by just calling {install,remove}_inhibitor one after
the other in code, but registering them on separate events triggers the issue,
e.g.:

    mp.observe_property('foo', nil, install_inhibitor)
    mp.observe_property('bar', nil, remove_inhibitor)

In particular, this happens during the script's "initialization": when
registering a property observer with mp.observe_property, the function is always
triggered once immediately. Per the [documentation][Lua API]:

> You always get an initial change notification. This is meant to initialize the
> user's state to the current value of the property.

I presume that there something funny going on when mp.command_native_async and
mp.abort_async_command get called in the same "tick" of the event loop, maybe
the cookie isn't properly registered and aborting then fails.

Anyway, since this problem seems to only occur during initialization, preventing
the inhibitor from being installed until the initialization is complete solves
the issue.

In order to delay the inhibitor until then, an observer is registered on a dummy
property 'plugin-initialized', and the registration is done after all the other
observers.

Technically it the documentation doesn't say that registration order is
respected for property observers (though it is mentioned that the registration
order is respected for event observers registered on the same event) but it
seems to work reliably.


## Debugging

Use mpv's `--msg-level` CLI option to increase the log level for messages from
this script, e.g.:

    mpv --msg-level=gnome_inhibit=debug --no-msg-color ...

Use `gnome-session-inhibit -l` to list the active inhibitors. When this script
is enabled and a video is playing, you should see

    mpv: video-playing (idle)


# TODO

- Allow configuring
  - Whether to inhibit at all when only audio is playing
  - Whether to inhibit idle (screen blanking) when only audio is playing
- Fix inhibitors not removed when mpv does not terminate gracefully, e.g. with
  `kill -9 <pid>`, either by having a wrapper around gnome-session-inhibit
  checking the parent PID (see https://stackoverflow.com/a/2035683), or by
  interfacing with dbus to open a session that gets disconnected if mpv
  terminates uncleanly (hopefully), or ...


[Disabling Screensaver]: https://mpv.io/manual/master/#disabling-screensaver
[Inhibit]: https://people.gnome.org/~mccann/gnome-session/docs/gnome-session.html#org.gnome.SessionManager.Inhibit
[jwz]: https://www.jwz.org/blog/2021/01/i-told-you-so-2021-edition/
[other applications]: https://unix.stackexchange.com/a/438335
[Lua API]: https://github.com/mpv-player/mpv/blob/master/DOCS/man/lua.rst

]]


local mp = require 'mp'
local msg = require 'mp.msg'

local cookie        -- Opaque token for the async gnome-session-inhibit command
local state = {}    -- Events cache to allow complex trigger conditions


-- -----------------------------------------------------------------------------
-- Inhibitor handlers
-- -----------------------------------------------------------------------------

local function install_inhibitor(evt, video)
    if cookie then return end

    cookie = mp.command_native_async(
        {
            name = 'subprocess',
            args = {
                'gnome-session-inhibit',
                '--inhibit-only',
                '--inhibit', (video and 'idle' or 'suspend'),
                '--app-id', 'mpv',
                '--reason', (video and 'video' or 'audio') .. ' playing',
            },

            -- `playback_only = true` does not kill the command when playback is
            -- paused (i.e. "pause" is still "playback == true") but also kills
            -- it immediately the first time. So we need to handle the paused
            -- state ourselves.
            playback_only = false,

            -- If not captured, mpv will just forward everything to stdout and
            -- stderr. Setting capture_stdXXX with capture_size = 0 will ensure
            -- that the command's output is discarded.
            capture_stdout = true,
            capture_stderr = true,
            capture_size = 0,
        },

        -- Should be optional according to the doc, but I get an error if I
        -- don't provide a function: attempt to call local 'cb' (a nil value)
        function() end
    )

    msg.verbose('inhibit on (' .. evt .. ')')
end

local function remove_inhibitor(evt)
    if not cookie then return end

    mp.abort_async_command(cookie)
    cookie = nil
    msg.verbose('inhibit off (' .. evt .. ')')
end


-- -----------------------------------------------------------------------------
-- State management
-- -----------------------------------------------------------------------------

-- Update the state and check if it changed. The third parameter allows to
-- compute more complex conditions over the state.
local function update_state(key, val, fn)
    fn = fn or function(state) return state[key] end

    local old = fn(state)
    state[key] = val
    local new = fn(state)

    msg.debug('state update:', key, '=', val, '/ fn:', old, '->', new)

    return new ~= old, new
end

-- Whether to enable inhibition is computed from several mpv properties.
-- Note: mpv's --keep-open option triggers a 'pause' event at the end of the
-- file, but --idle doesn't, and instead triggers an 'idle-active' event.
local function is_enabled()
    if not state['plugin-initialized'] then return false end
    if not state['stop-screensaver'] then return false end
    return not state['pause'] and not state['idle-active']
end

-- Whether mpv is playing a video. Note that when a video is started, this still
-- briefly returns false because mpv sends the corresponding event only after a
-- little while when the relevant subsystems have initialized.
local function is_video()
    return state['vo-configured']
end

-- -----------------------------------------------------------------------------
-- Event handlers
-- -----------------------------------------------------------------------------

-- Install or remove the inhibitor depending on the player's state
local function event_enable(evt, val)
    local changed, enabled = update_state(evt, val, is_enabled)
    if not changed then return end

    if enabled then
        install_inhibitor(evt, is_video())
    else
        remove_inhibitor(evt)
    end
end

-- Switch the type of inhibition depending on whether mpv is playing video or
-- only audio
local function event_video(evt, val)
    local changed, video = update_state(evt, val, is_video)
    if not changed then return end

    -- We only need to refresh the inhibitor if it's already installed,
    -- otherwise we can just wait for the next installation.
    if is_enabled() then
        remove_inhibitor(evt)
        install_inhibitor(evt, video)
    end
end

-- Handle the dummy 'plugin-initialized' event, indicating that all the other
-- events should have been fired once already to initialize the state.
local function event_ready(evt)
    mp.unobserve_property(event_ready)
    event_enable(evt, true)
end


-- -----------------------------------------------------------------------------
-- Wire everything together
-- -----------------------------------------------------------------------------

mp.observe_property('stop-screensaver', 'bool', event_enable)
mp.observe_property('pause', 'bool', event_enable)
mp.observe_property('idle-active', 'bool', event_enable)
mp.observe_property('vo-configured', 'bool', event_video)

-- Must be registered after all the other property observers, cf. work notes
mp.observe_property('plugin-initialized', nil, event_ready)

msg.info(
    'GNOME+Wayland idle inhibit workaround enabled.',
    'You can ignore the warning from the [vo/gpu/wayland] component.'
)
