function fish_prompt
    set -l last_status $status

    set -l normal (set_color normal)
    set -l usercolor (set_color $fish_color_user)
    set -l hostcolor (set_color $fish_color_host)
    set -l okcolor (set_color -o green)
    set -l errcolor (set_color -o red)
    set -l cwdcolor (set_color -o cyan)

    set -l arrow $okcolor
    test $last_status -ne 0
    and set arrow $errcolor
    if fish_is_root_user
        set -a arrow "#"
    else
        set -a arrow "➜"
    end
    set -a arrow "$normal "

    set -l cwd $cwdcolor(basename (prompt_pwd))$normal

    # Only show host if in SSH or container
    # Store this in a global variable because it's slow and unchanging
    if not set -q prompt_host
        set -g prompt_host ""
        if set -q SSH_TTY
            or begin
                command -sq systemd-detect-virt
                and systemd-detect-virt -q
            end
            set prompt_host $usercolor$USER$normal@$hostcolor$hostname$normal":"
        end
    end

    echo -n -s $arrow ' ' $prompt_host $cwd $normal ' '
end
