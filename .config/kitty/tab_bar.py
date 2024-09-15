from kitty.fast_data_types import (
    Screen,
    get_boss,
)
from kitty.tab_bar import (
    DrawData,
    ExtraData,
    TabBarData,
    as_rgb,
    draw_title,
    powerline_symbols,
)

def _ntabs(tab_id: int):
    for tm in get_boss().os_window_map.values():
        tab = tm.tab_for_id(tab_id)
        if tab is not None:
            return len(tm.tabs)
    return 1

# Computes the tab length such that all tabs have approx. the same size and the
# tab bar is filled.
def _tab_length(
    screen: Screen,
    tab_id: int,
    index: int, # 1-based
) -> int:
    ntabs = _ntabs(tab_id)
    ncols = screen.columns

    width = ncols // ntabs
    # compensate missing width m by adding 1 to m first tabs
    # TODO: Evenly distribute compensation instead
    width += 1 if (index <= ncols % ntabs) else 0
    return width - 1 # somehow length is 0-based

def draw_tab(
    draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    before: int,
    max_tab_length: int,
    index: int,
    is_last: bool,
    extra_data: ExtraData
) -> int:
    # Override kitty's tab length algorithm. We treat this as fixed length.
    max_tab_length = _tab_length(screen, tab.tab_id, index)
    if extra_data.for_layout:
        screen.cursor.x += max_tab_length
        return screen.cursor.x

    tab_bg = screen.cursor.bg
    tab_fg = screen.cursor.fg
    default_bg = as_rgb(int(draw_data.default_bg))

    if extra_data.next_tab:
        next_tab_bg = as_rgb(draw_data.tab_bg(extra_data.next_tab))
        needs_soft_separator = next_tab_bg == tab_bg
    else:
        next_tab_bg = default_bg
        needs_soft_separator = False

    separator_symbol, soft_separator_symbol = powerline_symbols.get(draw_data.powerline_style, ('', ''))
    min_title_length = 1 + 2
    start_draw = 2

    if screen.cursor.x == 0:
        screen.cursor.bg = tab_bg
        screen.draw(' ')
        start_draw = 1

    screen.cursor.bg = tab_bg
    if min_title_length >= max_tab_length:
        screen.draw('…')
    else:
        draw_title(draw_data, screen, tab, index, max_tab_length)
        extra = screen.cursor.x + start_draw - before - max_tab_length
        if extra > 0 and extra + 1 < screen.cursor.x:
            screen.cursor.x -= extra + 1
            screen.draw('…')

    if not needs_soft_separator:
        screen.draw(' ')
        if is_last:
            screen.draw(' ')
            if (e := screen.columns - screen.cursor.x) > 0:
                screen.draw(' ' * e)
        else:
            screen.cursor.fg = tab_bg
            screen.cursor.bg = next_tab_bg
            screen.draw(separator_symbol)
    else:
        prev_fg = screen.cursor.fg
        if tab_bg == tab_fg:
            screen.cursor.fg = default_bg
        elif tab_bg != default_bg:
            c1 = draw_data.inactive_bg.contrast(draw_data.default_bg)
            c2 = draw_data.inactive_bg.contrast(draw_data.inactive_fg)
            if c1 < c2:
                screen.cursor.fg = default_bg
        screen.draw(f' {soft_separator_symbol}')
        screen.cursor.fg = prev_fg

    end = screen.cursor.x
    if end < screen.columns:
        screen.draw(' ')
    return end
