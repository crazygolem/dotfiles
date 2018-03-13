# Directory containing this file, even if sourced
SDIR="${funcsourcetrace[1]%/*}"

# Common aliases
source ~/.commonrc

# Customized prompt
PS1='%F{yellow}%1~%f %# '
RPS1='%# %F{blue}%n%f@%F{blue}%m%f %D{%H:%M} !%!'

# Stuff
autoload -Uz compinit && compinit         # Tab completion

#setopt auto_pushd
#setopt autocd
unsetopt correct_all  # Disable autocorrection (if enabled)

# Executes expanded command immediately upon pressing [enter]
setopt no_hist_verify

# $DISPLAY is set by X and is available in graphical environments such as
# GNOME. It is not available in TTYs so we can discriminate using $DISPLAY
if [ $DISPLAY ]; then
  # Path to your oh-my-zsh configuration.
  ZSH=$HOME/.oh-my-zsh

  # Set name of the theme to load.
  # Look in ~/.oh-my-zsh/themes/
  # Optionally, if you set this to "random", it'll load a random theme each
  # time that oh-my-zsh is loaded.
  ZSH_THEME="robbyrussell"    # Default: robbyrussell

  # Set to this to use case-sensitive completion
  # CASE_SENSITIVE="true"

  # Comment this out to disable weekly auto-update checks
  # DISABLE_AUTO_UPDATE="true"

  # Uncomment following line if you want to disable colors in ls
  # DISABLE_LS_COLORS="true"

  # Uncomment following line if you want to disable autosetting terminal title.
  # DISABLE_AUTO_TITLE="true"

  # Uncomment following line if you want red dots to be displayed while waiting for completion
  COMPLETION_WAITING_DOTS="true"

  # Which plugins would you like to load? (plugins can be found in ~/.oh-my-zsh/plugins/*)
  # Custom plugins may be added to ~/.oh-my-zsh/custom/plugins/
  # Example format: plugins=(rails git textmate ruby lighthouse)
  plugins=(git svn mercurial screen compleat)

  source $ZSH/oh-my-zsh.sh

  export TERM='xterm-256color'  # Makes sure VIM displays colors nicely
fi

unset SDIR
