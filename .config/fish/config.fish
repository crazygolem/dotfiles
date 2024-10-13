if status is-interactive
    # ALT+X: Toggle private mode
    bind --user \ex 'if set -q fish_private_mode; exec fish; else; exec fish --private; end'

    if [ "$TERM" = xterm-kitty ]
        # Unlike most other terminal I've tested, in kitty clearing the screen
        # without clearing the scrollback buffer (i.e. `clear -x`) does not push
        # the current screen content into the scrollback buffer. I guess this is
        # more accurate regarding the original purpose of the `\e[2J` escape
        # sequence (clearing the screen for TUIs, not shells), but it's not what
        # I want. Kitty provides an alternative escape sequence for this:
        # `\e[22J`. This is not documented in kitty's protocol extensions pages,
        # but it is mentioned in the "Reset the terminal" section [1] of the
        # keyboard shortucts.
        #
        # [1]: https://sw.kovidgoyal.net/kitty/conf/#shortcut-kitty.Reset-the-terminal
        bind --user \cl 'printf \e\[H\e\[22J; commandline -f repaint'

        # Kitty does not advertise the 'E3' capability (cf. `man 5 user_caps`,
        # and [1] for kitty's rationale for doing so) in its terminfo file, even
        # though it fully supports it. This basically breaks the `clear`
        # command, making kitty behave like an outdated terminal that doesn't
        # support clearing the scrollback buffer. There is no clean way to fix
        # `clear` and make it behave as expected under kitty, so instead the
        # escape sequence is hardcoded here :(
        #
        # [1]: https://github.com/kovidgoyal/kitty/issues/6255
        bind --user \e\cl 'printf \e\[H\e\[2J\e\[3J; commandline -f repaint'
    else
        # CTRL+L: Clears the screen but not the scrollback buffer
        # Mapped by default to fish's `clear-screen` input command that does the
        # right thing under most TTYs.

        # CTRL+ALT+L: Clear screen like real men do.
        bind --user \e\cl 'clear; commandline -f repaint'
    end
end
