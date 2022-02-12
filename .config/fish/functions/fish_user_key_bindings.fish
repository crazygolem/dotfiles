function fish_user_key_bindings --description "User key bindings"
    bind --user \ex 'if set -q fish_private_mode; exec fish; else; exec fish --private; end'
end
