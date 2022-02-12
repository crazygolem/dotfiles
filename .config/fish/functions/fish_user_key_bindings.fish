function fish_user_key_bindings --description "User key bindings"
    # ALT+X: Toggle private mode
    bind --user \ex 'if set -q fish_private_mode; exec fish; else; exec fish --private; end'

    # CTRL+ALT+L: Clear screen like real men do.
    bind --user \e\cl 'clear; commandline -f repaint'
end
