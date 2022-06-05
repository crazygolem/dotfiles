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


# Debugging

Use mpv's `--msg-level` CLI option to increase the log level for messages from
this script, e.g.:

    mpv --msg-level=gnome_inhibit=debug --no-msg-color ...

Use `gnome-session-inhibit -l` to list the active inhibitors. When this script
is enabled and a video is playing, you should see

    mpv: video-playing (idle)


# TODO

- Do not inhibit for audio-only playback, only for video
- Fix inhibitors not removed when mpv does not terminate gracefully, e.g. with
  `kill -9 <pid>`, either by having a wrapper around gnome-session-inhibit
  checking the parent PID (see https://stackoverflow.com/a/2035683), or by
  interfacing with dbus to open a session that gets disconnected if mpv
  terminates uncleanly (hopefully), or ...
- Investigate whether the 'playback-abort' event should be handled
- Only inhibit when the player is visible


[Disabling Screensaver]: https://mpv.io/manual/master/#disabling-screensaver
[Inhibit]: https://people.gnome.org/~mccann/gnome-session/docs/gnome-session.html#org.gnome.SessionManager.Inhibit
[jwz]: https://www.jwz.org/blog/2021/01/i-told-you-so-2021-edition/
[other applications]: https://unix.stackexchange.com/a/438335

]]


local mp = require 'mp'
local msg = require 'mp.msg'

local cookie        -- Opaque token for the async gnome-session-inhibit command
local state = {}    -- Events cache to allow complex trigger conditions

-- Update the state and check if it changed. The third parameter allows to
-- compute more complex conditions over the state.
local function update_state(key, val, fn)
    fn = fn or function(state) return state[key] end
    local old = fn(state)
    state[key] = val
    local new = fn(state)
    msg.debug('State update:', key, '=', val, '/ fn:', old, '->', new)
    return new ~= old, new
end

-- "Paused" for the purpose of inhibitors is computed from several mpv
-- properties, because when becoming idle, mpv doesn't fire the 'pause' event.
local function is_paused()
    -- When uninitialized, we consider mpv's state to be paused, i.e.
    -- effectively nil is equivalent to true in this case.
    return state['pause'] ~= false or state['idle-active'] ~= false
end

-- Whether mpv is playing a video
local function is_video()
    -- nil is equivalent to false, forcing a boolean ensures that initializing
    -- to false isn't considered a change.
    return not not state['vo-configured']
end

local function install_inhibitor(evt, video)
    if not cookie then
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

                -- `playback_only = true` does not kill the command when
                -- playback is paused (i.e. "pause" is still "playback == true")
                -- but also kills it immediately the first time.
                -- So we need to handle the paused state ourselves.
                playback_only = false,

                -- If not captured, mpv will just forward everything to stdout
                -- and stderr. Setting capture_stdXXX with capture_size = 0 will
                -- ensure that the command's output is discarded.
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
end

local function remove_inhibitor(evt)
    if cookie then
        -- FIXME: If abort_async_command is executed too fast after
        -- command_native_async, it seems sometimes it fails to abort the
        -- command. This often happen at the very start when initializing the
        -- script, and when mpv fires a bunch of property-change events in quick
        -- succession, which causes inhibitors to be installed and removed too
        -- fast.
        os.execute('sleep 0.1')

        mp.abort_async_command(cookie)
        cookie = nil
        msg.verbose('inhibit off (' .. evt .. ')')
    end
end


-- Install or remove the inhibitor depending on the player's state
local function event_pause(evt, val)
    local changed, paused = update_state(evt, val, is_paused)
    if not changed then return end

    if paused then
        remove_inhibitor(evt)
    else
        install_inhibitor(evt, is_video())
    end
end

-- Switch the type of inhibition depending on whether mpv is playing video or
-- only audio
local function event_voconfigured(evt, val)
    local changed, video = update_state(evt, val, is_video)
    if not changed then return end

    -- We only need to refresh the inhibitor if it's already installed,
    -- otherwise we can just wait for the next installation.
    if not is_paused() then
        remove_inhibitor(evt)
        install_inhibitor(evt, video)
    end
end

-- Switch the whole handling of inhibition
local function event_inhibit(_, enabled)
    if enabled then
        mp.observe_property('pause', 'bool', event_pause)
        mp.observe_property('idle-active', 'bool', event_pause)
        mp.observe_property('vo-configured', 'bool', event_voconfigured)
        msg.verbose('inhibit handling on')
    else
        mp.unobserve_property(event_pause)
        mp.unobserve_property(event_voconfigured)
        remove_inhibitor()
        msg.verbose('inhibit handling off')
    end
end

mp.observe_property('stop-screensaver', 'bool', event_inhibit)
