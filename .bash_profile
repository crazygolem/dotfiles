source "$HOME"/.profile

if [[ $- = *i* ]] && [[ -f "$HOME"/.bashrc ]]; then
  source "$HOME"/.bashrc
fi
