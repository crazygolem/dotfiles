# Directory containing this file, even if sourced
SDIR="${BASH_SOURCE[0]%/*}"

# Common aliases
source ~/.commonrc

# Poor man's autocompletion (in case bash-completion is not installed)
complete -cf man sudo

# Proper autocompletion
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi


# Customized prompt
#           green      no col         green           no col       blue          no col
PS1='\[\033[1;32m\]\u\[\033[00m\]@\[\033[1;32m\]\h\[\033[00m\]:\[\033[1;34m\]\W\[\033[00m\]\$ '

unset SDIR
