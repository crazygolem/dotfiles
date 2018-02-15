# Directory containing this file, even if sourced
SDIR="${BASH_SOURCE[0]%/*}"

# Common aliases
source ~/.commonrc

# Poor man's autocompletion (in case bash-completion is not installed)
complete -cf man sudo

# Customized prompt
#           green      no col         green           no col       blue          no col
PS1='\[\033[1;32m\]\u\[\033[00m\]@\[\033[1;32m\]\h\[\033[00m\]:\[\033[1;34m\]\W\[\033[00m\]\$ '

unset SDIR
