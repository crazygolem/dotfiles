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
    draw_title,
    template_has_field,
)

from wcwidth import (
    wcswidth as wlen,
    wcwidth as wclen,
)


_opts = get_options()

_separator_symbols: dict[str, tuple[str, str]] = {
    'simple':   ('▌', '│'),
    'dashed':   ('▌', '┊'),
    'angled':   ('', ''),
    'slanted':  ('', '╱'),
    'rounded':  ('', ''),
}

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

        l = wclen(c)
        wi += l
        if wi > n:
            raise Exception(f"Index {n} in '{s}' is within the wide character '{c}'.")
        first += c

    return (first, last)


def _draw_title(
    draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    index: int,
    max_title_length: int = 0
) -> None:
    def make_title(tpl):
        tpl_has_notif = any(map(
            lambda s: template_has_field(tpl, s),
            ['bell_symbol', 'activity_symbol']
        ))

        status = ''
        length = '0'

        status += "{' ' if layout_name == 'stack' else ''}"
        length += "+ (2 if layout_name == 'stack' else 0)"

        if not tpl_has_notif:
            status += "{bell_symbol or activity_symbol}"
            length += f"+ ({wlen(draw_data.bell_on_tab)} if bell_symbol else 0)"
            length += f"+ ({wlen(draw_data.tab_activity_symbol)} if not bell_symbol and activity_symbol else 0)"

        if tpl_has_notif:
            status += "{' ' if layout_name == 'stack' else ''}"
            length += "+ (1 if layout_name == 'stack' else 0)"
        else:
            status += "{' ' if layout_name == 'stack' or bell_symbol or activity_symbol else ''}"
            length += "+ (1 if layout_name == 'stack' or bell_symbol or activity_symbol else 0)"

        # Status length is removed twice when centering to avoid status items
        # causing the title to shift (if there is enough space). It must then
        # be compensated on the right once, to avoid status items causing the
        # tab to change size.
        return f'{status}{{f"{tpl}".center(max_title_length - ({length}) * 2).ljust(max_title_length - ({length}))}}'

    draw_data = draw_data._replace(title_template = make_title(draw_data.title_template))
    if draw_data.active_title_template is not None:
        draw_data = draw_data._replace(active_title_template = make_title(draw_data.active_title_template))

    draw_title(draw_data, screen, tab, index, max_title_length)



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

    sep = _opts.tab_separator
    separator_symbol, soft_separator_symbol = _separator_symbols.get(sep) or (
        ('▌', sep) if (l := wlen(sep)) == 1
        else wsplit(sep, l // 2) if l % 2 == 0
        else _separator_symbols.get('simple')
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
        _draw_title(draw_data, screen, tab, index, max_tab_length - 2)
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
