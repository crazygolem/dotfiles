""" Crazygolem's vimrc """""""""""""""""""""""""""""""""""""""""""""""""""""""
"
" This vimrc file provides graceful degradation if Vundle or some bundles are
" not installed. Restricted mode provides an enhanced status line, a lot of
" usability and mappings to basic functions.
"
" Corollary: You can copy this file in root's home directory to have a
" minimally usable vim (also statically copy the color scheme in root's
" ~/.vim/colors otherwise you won't have nice colors)
"
" TODO: Gracefully degrade mappings to bundle functions
" TODO: Update Vundle
"
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

set nocompatible               " be iMproved


"""""" Vundle """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

function! Vundleize()
  " Brief help
  " :BundleList          - list configured bundles
  " :BundleInstall(!)    - install(update) bundles
  " :BundleSearch(!) foo - search(or refresh cache first) for foo
  " :BundleClean(!)      - confirm(or auto-approve) removal of unused bundles
  "
  " see :h vundle for more details or wiki for FAQ
  " NOTE: comments after Bundle command are not allowed..

  set rtp+=~/.vim/bundle/vundle " Must be manually cloned to bootstrap vundle
  call vundle#rc()

  " Let Vundle manage Vundle (required)
  Bundle 'gmarik/vundle'

  " Color themes (makes them available, does not select one)
  Bundle 'vim-scripts/wombat256.vim'
  Bundle 'altercation/vim-colors-solarized'

  " Create directories in path if they don't exist yet
  Bundle 'auto_mkdir'

  " Omni completion on ctrl-space (default <tab> is too intrusive/frustrating)
  " <c-space> cannot be mapped in vim console; <nul> is equivalent
  Bundle 'ervandew/supertab'
  let g:SuperTabMappingForward='<nul>'
  let g:SuperTabMappingBackward='<s-nul>'

  " Modification tree
  Bundle 'sjl/gundo.vim'

  " Buffer list
  Bundle 'fholgado/minibufexpl.vim'

  " Show CSS colors
  Bundle 'ap/vim-css-color'

  " Dummy text generator
  Bundle 'vim-scripts/loremipsum'

  " xterm color table, for scheme customization
  Bundle 'xterm-color-table.vim'

  " File browser
  Bundle 'The-NERD-tree'

  " Toggle mouse between vim and terminal capture
  Bundle 'toggle_mouse'

  " Show syntax attribute of the character under cursor
  Bundle 'SyntaxAttr.vim'

  " Table formatting
  Bundle 'dhruvasagar/vim-table-mode'
  let g:table_mode_corner='|' " Markdown-compatible tables

  " Text alignment
  Bundle 'godlygeek/tabular'
endfunction

silent! call Vundleize()


""" General """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Defines <leader>
let mapleader = 'é'           " Very accessible on fr-CH layout

" Set vim's internal encoding (not files encoding!)
set encoding=utf-8            " Required to display Unicode glyphs


" Force write, with alias for backward compatibility with muscle memory
" TODO: Delete the view after it has been reloaded, to prevend surprises in
" some edge cases (e.g. if for some reason 'viewoptions' is not set correctly,
" see 'Buffers' section).
" FIXME: The buffer is reloaded also if write is aborted, e.g. when using ^C
" instead of giving the password to sudo.
command! W :execute ':silent w !sudo tee % > /dev/null'
      \ | :silent! mkview | :edit! | :silent! loadview
cmap w!! W

" Prevent mistakenly using ':X' instead of ':x'
" Source: http://stackoverflow.com/a/17794801
" Side-effect: prevents encryption altogether. Use ':una X' to disable this
" security or run vim with -x argument.
cnorea <expr> X (getcmdtype() is# ':' && getcmdline() is# 'X') ? 'x' : 'X'

" Word wrapping
set wrap
set linebreak
set display=truncate          " Show '@@@' in the last line if it is truncated

" Syntactic coloration
syntax on

"
""" Color scheme """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" Use Vundle to install them, or copy them manually in ~/.vim/colors
" If none is available, the default scheme will be used.

" Wombat256
silent! colorscheme wombat256mod
silent! colorscheme wombat256mod-patch-solarized

" Solarized
" This color scheme takes advantage of the Solarized theme for terminal
" emulators. If it is not available or not used, a compatibility mode is
" available, but it looks inferior.
"let g:solarized_termcolors=256   " Uncomment to activate the degraded mode
"set background=dark              " Uncomment if vim detection is ineffective
"silent! colorscheme solarized


""" Line numbers """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" Relative line numbers: see the 'Keymaps' section

set number
set numberwidth=5


""" Cursor """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" For some reason, unlike vim neovim does not have cursor blinking by default.
" The following configuration has been takend from nvim's `:help 'guicursor'`.
set guicursor+=a:blinkwait700-blinkoff400-blinkon250-Cursor/lCursor
              \,sm:block-blinkwait175-blinkoff150-blinkon175


""" Mouse """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

set mouse=a                   " Use mouse to click
set mousehide                 " Hide mouse pointer when typing


""" Formatting """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

set formatoptions+=j          " Removes comment leader when joining comments

" Indentation and tabs
set expandtab                 " Convert tabs to spaces
set tabstop=2                 " Tab width is 2 spaces
set softtabstop=2             " Same as 'tabstop'
set shiftwidth=2              " Same as 'tabstop' (used by <c-d>)
set smarttab                  " Smart tabbing on front of lines
set autoindent                " Use same indentation as previous line
set smartindent               " Auto indent with braces, etc.

" Enable <Tab> to indent several times
vnoremap < <gvgv
vnoremap > >gvgv
vnoremap <Tab> >gvgv
vnoremap <S-Tab> <gvgv
noremap <Tab> >>
noremap <S-Tab> <<


""" Search and replace """""""""""""""""""""""""""""""""""""""""""""""""""""""

set ignorecase          " Searches are case-insensitive...
set smartcase           " ... except when pattern contains uppercase letters
set gdefault            " Inverts meaning of 'g' flag in substitutions
set incsearch           " Real-time matching
set hlsearch            " Highlight matches

" Remove current search highlight (see 'Keymaps' section for mapping)
function! RemoveSearchHighlight()
  let @/ = ""
endfunction


""" Navigation & Cursor positioning """"""""""""""""""""""""""""""""""""""""""

" Give some context when the cursor is near the border
set scrolloff=5              " Set to 999 for 'always at mid-screen'

" Highlight current line in insert mode
autocmd InsertEnter * set cursorline
autocmd InsertLeave * set nocursorline

" Jump to the next row in long wrapped line (instead of next actual line)
nnoremap k gk
nnoremap j gj
map <up> k
imap <up> <c-o><up>
map <down> j
imap <down> <c-o><down>
nnoremap gk k
nnoremap gj j

" Move cursor beyond last character
set virtualedit=onemore

" Do not move the cursor left when returning to normal mode from insert mode
" Very nice and intuitive with 'virtualedit=onemore'. Also makes a sound when
" the cursor cannot stay in place (e.g. when there is no virtualedit and the
" cursor has to move left at the end of the line)
imap <C-c> <C-c>l

" Fix navigation (ctrl+arrow) in TMUX with 'screen' terminal and 'xterm-keys'
" option enabled.
if &term =~ '^screen'
    execute "set <xUp>=\e[1;*A"
    execute "set <xDown>=\e[1;*B"
    execute "set <xRight>=\e[1;*C"
    execute "set <xLeft>=\e[1;*D"
endif


""" Statusline """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

set laststatus=2              " Always display status line

set statusline=%t             " tail of the filename
set statusline+=\ %3(%m%)     " modified flag
set statusline+=%r            " read only flag
set statusline+=[%{strlen(&fenc)?&fenc:'none'}, " file encoding
set statusline+=%{&ff}]       " file format
set statusline+=%y            " filetype
set statusline+=%=            " left/right separator
set statusline+=%7(%v:%{virtcol('$')-1}%)       " column / line length
set statusline+=\ %11(☰\ %l:%L%)                " line / total lines
set statusline+=\ %P          " percent through file

set showcmd                   " Show typed commands and selection length
set wildmenu                  " Display completion matches in the status line
set showmode                  " Show current mode (if not normal mode)

" Status line context colors
hi StatusLineNC ctermbg=235   " Background color for not-current window

function! ColorizeStatusLine()
  " Context-dependent color indication, to help determine how a file can be
  " written.
  " TODO: Check if vim can determine if a file is writeable as root when
  " non-root.
  "
  "       User      Root
  " :w    Gray      Red
  " :w!   Blue      Green
  " :W    Purple    -
  " N/A   White     White
  "

  " Save default values (defined by the color scheme)
  if (!exists('b:sl_ctermbg'))
    let b:sl_ctermbg = synIDattr(synIDtrans(hlID('StatusLine')),'bg')
    if (index(['-1', ''], b:sl_ctermbg) > -1)
      let b:sl_ctermbg = 'None'
    endif
  endif
  if (!exists('b:sl_ctermfg'))
    let b:sl_ctermfg = synIDattr(synIDtrans(hlID('StatusLine')), 'fg')
    if (index(['-1', ''], b:sl_ctermfg) > -1)
      let b:sl_ctermfg = 'None'
    endif
  endif

  " Colorize status line
  if !&l:modifiable
    hi StatusLine ctermbg=15 ctermfg=0  " White
  else
    exec ':hi StatusLine ctermfg='.b:sl_ctermfg
    if &l:readonly
      if $USER == 'root'
        hi StatusLine ctermbg=28        " Green
      else
        hi StatusLine ctermbg=31        " Light blue
      endif
    else
      if $USER == 'root'
        hi StatusLine ctermbg=1         " Red
      else
        exec ':hi StatusLine ctermbg='.b:sl_ctermbg
      endif
    endif
  endif
endfunction

" Set and update the status line color when needed.
" The CursorHold events are used as fallback for the cases that cannot be
" tracked, typically `:set ro!` (there is no event to track the change of a
" flag). The colorization is not immediate, but at least it is eventually
" performed. This solution is far from perfect, and sometimes even does not
" work...
augroup SlColorize
  autocmd!
  autocmd BufEnter * call ColorizeStatusLine()
  autocmd WinEnter * call ColorizeStatusLine()
  autocmd BufWritePost * call ColorizeStatusLine()            " E.g. using :w!
  autocmd FileChangedShellPost * call ColorizeStatusLine()
  autocmd InsertEnter,InsertLeave * call ColorizeStatusLine()
  autocmd CursorHold,CursorHoldI * call ColorizeStatusLine()  " Fallback
augroup END


""" Invisible stuffs and landmarks """""""""""""""""""""""""""""""""""""""""""

" List of invisible characters and their visible replacement
set listchars=eol:↲,tab:⇥\ ,trail:·,extends:»,precedes:«,nbsp:⎵

" Toggles the visibility of invisible characters and of the right margin
" delimiter.
" If called with an argument, it is used to set the right margin delimiter.
" Example: ToggleInvisible('+2,80,100,120')
function! ToggleInvisible(...)
  if a:0 > 0
    let b:ti_cc = a:1
  elseif !exists('b:ti_cc')
    if &textwidth > 0
      let b:ti_cc = '+2'
    else
      let b:ti_cc = '80'
    endif
  endif

  if &colorcolumn == b:ti_cc
    let &colorcolumn = 0
    set nolist
  else
    let &colorcolumn = b:ti_cc
    set list
  endif
endfunction


""" Miscellaneous """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Fix terminal timeout when pressing escape
function! ToggleEscTimeout()
  if ! has('gui_running')
      set ttimeoutlen=10
      augroup FastEscape
          autocmd!
          au InsertEnter * set timeoutlen=0
          au InsertLeave * set timeoutlen=1000
      augroup END
  endif
endfunction

"call ToggleEscTimeout()   " Disabled: I use <C-c> instead: always fast


" Prevents modification of readonly files
"au BufEnter * if &l:ro | set nomodifiable | endif


""" Buffers """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Stateful buffers (remembers folds, cursor position)
set viewoptions-=options                " Prevents surprises (e.g. nonumber)
autocmd BufWinLeave * silent! mkview    " Save buffer state
autocmd BufWinEnter * silent! loadview  " Load buffer state


""" Keymaps """"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

" Toggle invisible characters
map <F4> :call ToggleInvisible()<CR>
map! <F4> <C-o><F4>

" Toggle paste mode
set pastetoggle=<F2>

" Remove search highlight
noremap <leader>/ :call RemoveSearchHighlight()<CR>

" Toggle relative numbers
nnoremap <Leader>r :set relativenumber!<CR>

" Split screen
nnoremap <leader>s :vsplit<CR>        " Quick access to my favorite one
nnoremap <leader>ss :vsplit<CR>       " Even quicker access to my favorite one
nnoremap <leader>sx :split<CR>        " 'x' is kind of 'below'
nnoremap <leader>sd :vsplit<CR>       " For consistency

" Highlight current line temporarily (for when I'm lost)
nnoremap <leader>l :set cursorline!<CR>

" Toggle syntax group debugging
" Requires the HiLinkTrace plugin by Charles E. Campbell (aka. Dr Chip)
" Source: http://www.drchip.org/astronaut/vim/index.html#HILINKS
map <S-F9> :HLT!<CR>

" Lighter version of syntax group debugging
map <F9> :call SyntaxAttr()<CR>

" Constrained editing
map <F3> :call ToggleConstrained()


""" That's all Folks! """"""""""""""""""""""""""""""""""""""""""""""""""""""""
