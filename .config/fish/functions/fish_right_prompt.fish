function fish_right_prompt --description "Write out the right prompt"
    set -l blue (set_color blue)
    set -l bmag (set_color -o magenta)
    set -l norm (set_color normal)

    if set -q fish_private_mode
        set -a prompt $bmag '<><' $norm ' '
    else
        set -a prompt '<><' ' '
    end

    set -a prompt $blue $USER $norm @ $blue $hostname $norm ' '
    set -a prompt (date +%H:%M) ' '

    echo -n -s $prompt
end
