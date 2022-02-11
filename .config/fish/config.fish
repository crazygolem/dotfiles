if status is-interactive
    # Commands to run in interactive sessions can go here

    # Clear screen like real men do. (ctrl-alt-L)
    bind \e\cl 'clear; commandline -f repaint'
end
