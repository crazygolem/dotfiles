from kitty.fast_data_types import (
    Screen,
    get_boss,
    get_options,
)
from kitty.tab_bar import (
    DrawData,
    ExtraData,
    TabBarData,
    as_rgb,
    draw_title as kitty_draw_title,
    safe_builtins,
)

from wcwidth import (
    wcswidth,
    wcwidth,
)

# Patch Kitty's tab_bar script to allow extra functions in the title template.
# `dlen` (Display Length) correctly computes string length for display, where
# wide characters take up two cells. This makes it easier to correctly compute
# widths to get fixed tab sizes.
safe_builtins['dlen'] = wcswidth


separator_symbols: dict[str, tuple[str, str]] = {
    'simple':   ('▌', '│'),
    'dashed':   ('▌', '┊'),
    'angled':   ('', ''),
    'slanted':  ('', '╱'),
    'rounded':  ('', ''),
}

# Returns the number of tabs in the os window that contains the specified tab.
def num_tabs(tab_id: int):
    for tm in get_boss().os_window_map.values():
        tab = tm.tab_for_id(tab_id)
        if tab is not None:
            return len(tm.tabs)
    return 1

# Computes the tab length such that all tabs have approx. the same size and the
# tab bar is filled.
def tab_length(
    screen: Screen,
    tab_id: int,
    index: int, # 1-based
) -> int:
    ntabs = num_tabs(tab_id)
    ncols = screen.columns

    width = ncols // ntabs
    # compensate missing width m by adding 1 to m first tabs
    width += 1 if (index <= ncols % ntabs) else 0
    return width - 1 # somehow length is 0-based

# Splits a string at length `n`, considering wide charactes that display on two
# cells as being of length 2.
def wsplit(s: str, n: int) -> tuple[str, str]:
    first = ''
    last = ''
    wi = 0
    for i, c in enumerate(s):
        if wi >= n:
            last = s[i:]
            break

        l = wcwidth(c)
        wi += l
        if wi > n:
            raise Exception(f"Index {n} in '{s}' is within the wide character '{c}'.")
        first += c

    return (first, last)

# Wrapper for Kitty's `draw_title` function that aligns the status zone and the
# title correctly, making sure to preserve the expected tab size.
def draw_title(
    draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    index: int,
    max_title_length: int = 0
) -> None:
    def make_title(tpl: str) -> str:
        if tpl is None:
            return None

        (_, status, sep, title, *_) = tpl.split(tpl[0], 5)

        status += f'{{f"{sep}" if f"{status}" else ""}}'
        length = f'dlen(f"{status}")'

        # Apply corrections if the title contains wide characters.
        max_length = f'max_title_length - (dlen(f"{title}") - len(f"{title}"))'

        # Status length is removed twice when centering to avoid status items
        # causing the title to shift (if there is enough space). It must then
        # be compensated on the right once, to avoid status items causing the
        # tab to change size.
        return f'{status}{{f"{title}".center(({max_length}) - ({length}) * 2).ljust(({max_length}) - ({length}))}}'

    draw_data = draw_data._replace(
        title_template = make_title(draw_data.title_template),
        active_title_template = make_title(draw_data.active_title_template),
    )

    kitty_draw_title(draw_data, screen, tab, index, max_title_length)


# Draws the tab bar as a fullwidth bar with tabs of equal size.
# Based on Kitty's `draw_tab_with_powerline`.
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
    max_tab_length = tab_length(screen, tab.tab_id, index)
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

    sep = get_options().tab_separator
    separator_symbol, soft_separator_symbol = separator_symbols.get(sep) or (
        ('▌', sep) if (l := wcswidth(sep)) == 1
        else wsplit(sep, l // 2) if l % 2 == 0
        else separator_symbols.get('simple')
    )

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
        draw_title(draw_data, screen, tab, index, max_tab_length - 2)
        extra = screen.cursor.x + start_draw - before - max_tab_length
        if extra > 0 and extra + 1 < screen.cursor.x:
            screen.cursor.x -= extra + 1
            screen.draw('…')

    if not needs_soft_separator:
        screen.draw(' ')
        if is_last:
            # Replaces the separator so it fits the edge of the screen
            screen.draw(' ')
            # Should not happen as we increase tab width such that the bar gets
            # completely filled, but if anything weird happens we cover past the
            # last tab so that the "inactive" background doesn't show.
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
