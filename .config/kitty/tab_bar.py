"""
Provides a full-width tab bar, with evenly-sized tabs that don't vary based on
their content.

The tabs' title is split into a status zone aligned to the left, and the title
zone which gets centered if space permits.

COMPATIBILITY

This plugins requires python >= 3.12, as it relies on some improvements to
f-strings handling that were introduced with PEP 701, notably quote reuse in
nested f-strings.

CONFIGURATION

tab_bar_style       custom
tab_separator       simple|dashed|angled|slanted|rounded|"<1-char>"|"<2n-chars>"
tab_title_template  "<d><status><d><separator><d><title>"

Where:
    <1-char>        is a character displayed on a single column.
    <2n-char>       is a string displayed on an even number of columns and that
                    can be split in half, with the first half being used for the
                    "hard" tab separator (on the active tab), and the second
                    half for the "soft" tab separator (between background tabs).
    <d>             is a delimiter that does not appear in the status, separator
                    or title templates.
    <status>        is a template used for the status zone.
    <separator>     is a template displayed after the status if the status zone
                    is not empty.
    <title>         is a template used for the tab's title.
"""

from functools import lru_cache

from kitty.fast_data_types import Screen, get_boss, get_options, wcswidth
from kitty.tab_bar import DrawData, ExtraData, TabBarData, as_rgb
from kitty.tab_bar import draw_title as kitty_draw_title
from kitty.tab_bar import safe_builtins


# Patch Kitty's tab_bar script to allow extra functions in the title template.
# As Kitty's draw_title function is used to render the title templates, it's
# easier to inject some helper functions in the title template than attempt to
# predict what will be rendered to correct for it, track what's been rendered to
# fix afterwards, or to pre-render the templates ourselves.
safe_builtins['dlen'] = lru_cache(wcswidth)     # display length


separator_symbols: dict[str, tuple[str, str]] = {
    'simple':   ('▌', '│'),
    'dashed':   ('▌', '┊'),
    'angled':   ('', ''),
    'slanted':  ('', '╱'),
    'rounded':  ('', ''),
}

def title_length(
    screen: Screen,
    index: int, # 1-based
    sep_width: int,
) -> int:
    """
    Computes the title length for the current tab, such taht all tabs have about
    the same title size, ensuring that the tab bar is filled exactly.
    This assumes no separator before the first tab and after the last, and all
    separators having the same size.
    """

    ntabs = len(get_boss().active_tab_manager.tabs)
    ncols = screen.columns - (ntabs - 1) * sep_width

    width = ncols // ntabs
    # Compensate missing width m by adding 1 to first m tabs. There is always at
    # least m tabs (pigeonhole principle).
    width += 1 if (index <= ncols % ntabs) else 0
    return width

@lru_cache
def wsplit(s: str, n: int) -> tuple[str, str]:
    """
    Greedily splits a string at column `n`, taking into account wide characters
    and graphene clusters.
    """

    if n < 0:
        return ('', s)

    for i in range(len(s) + 1):
        l = wcswidth(s[:i])
        if l < n:
            continue
        elif l > n:
            c = wsplit(s[i-1:], 2)[0]
            raise Exception(f"Column {n} in '{s}' splits the wide character {c}.")

        for i in range(i, len(s)):
            l = wcswidth(s[:i+1])
            if l > n:
                return (s[:i], s[i:])
        break
    return (s, '')

def cfg_separator(
    draw_data: DrawData,
    screen: Screen,
    extra_data: ExtraData
) -> tuple[str, bool]:
    sep_cfg = get_options().tab_separator
    sep_hard, sep_soft = separator_symbols.get(sep_cfg) or (
        ('▌', sep_cfg) if (l := wcswidth(sep_cfg)) == 1
        else wsplit(sep_cfg, l // 2) if l % 2 == 0
        else separator_symbols.get('simple')
    )

    # Checking using colors instead of tab.is_active, because users could choose
    # to highlight active tab in other ways, and the soft/hard distinction for
    # separators is only a colors thing.
    tab_bg = screen.cursor.bg
    next_tab_bg = as_rgb(draw_data.tab_bg(extra_data.next_tab)) if extra_data.next_tab else None
    sep = sep_hard if next_tab_bg and next_tab_bg != tab_bg else sep_soft

    return (sep is sep_hard, sep, wcswidth(sep), next_tab_bg)

def draw_title(
    draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    index: int,
    title_length: int = 0
) -> None:
    """
    Wrapper for Kitty's `draw_title` function that aligns the status zone and
    the title correctly, making sure to preserve the expected tab size.
    """

    @lru_cache
    def make_title(tpl: str) -> str:
        if tpl is None:
            return None

        (_, status, sep, title, *_) = tpl.split(tpl[0], 5)

        # Those variables contain a template, so we can only embed them in the
        # final template to get evaluated when the tab is rendered. In
        # particular, their length can't be computd before ahead of time (that
        # is, without evaluating the template ourselves).
        # To protect the template against whatever f-string embedding Kitty is
        # doing, and in particular to allow quote reuse, the variables should
        # always be embedded in an expression component in the final template.
        status = 'f"""' + status + '"""'
        sep = 'f"""' + sep + '"""'
        title = 'f"""' + title + '"""'

        status = f'{{(_s := (_s := {status}) + ({sep} if _s else ""))}}'

        # Apply corrections if the title contains wide characters.
        max_length = 'max_title_length - (dlen(_t) - len(_t))'

        # Status length is removed from left and right of title to avoid status
        # items causing the title to shift (if there is enough space).
        # It should then be compensated on the right to avoid the tab itself
        # changing size, but this can easily be done after the title has been
        # drawn, without having to compute the rendered size of the status or
        # title.
        title = f'{{(_t := {title}).center(({max_length}) - dlen(_s) * 2)}}'

        # Disable Kitty's backward compatibility mode "automatically prepend
        # {bell_symbol} and {activity_symbol} if not present".
        #
        # This is necessary because otherwise it breaks the tab bar when a tab
        # wants to show a missing symbol.
        #
        # This is caused by Kitty using `string.Formatter.parse` to check if
        # they are missing, which parses the `string.format` mini-language, not
        # the f-string templates that support arbitrary python expressions and
        # in particular nested f-strings. The format mini-language parser borks
        # on nested f-strings as soon as a nested interpolation is encountered.
        # For rendering the template, Kitty evaluates f-strings and does not
        # rely on `string.format`, so nested f-strings are otherwise not an
        # issue.
        #
        # Adding a noop using those variables at the beginning of the template
        # solves the issue because Kitty lazily parses the template until the
        # variables are found, and if they appear early the routine won't reach
        # nested f-strings where the parser borks.
        nocompat = '{"" and bell_symbol and activity_symbol}'

        return nocompat + status + title

    draw_data = draw_data._replace(
        title_template = make_title(draw_data.title_template),
        active_title_template = make_title(draw_data.active_title_template),
    )

    before = screen.cursor.x
    kitty_draw_title(draw_data, screen, tab, index, title_length)
    extra = screen.cursor.x - before - title_length
    if extra < 0:
        screen.draw(' ' * -extra)
    elif extra > 0 and extra + 1 < screen.cursor.x:
        screen.cursor.x -= extra + 1
        screen.draw('…')


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
    """
    Draw the tab bar as a fullwidth bar with tabs of equals size.
    Inspired by Kitty's `draw_tab_with_powerline`.
    """

    (sep_is_hard, sep, sep_width, next_tab_bg) = cfg_separator(
        draw_data, screen, extra_data)

    # Override kitty's tab length algorithm. We treat this as fixed length.
    max_title_length = title_length(screen, index, sep_width)
    max_tab_length = max_title_length + (sep_width if not is_last else 0)

    # Early exit for layout-only call
    if extra_data.for_layout:
        screen.cursor.x += max_tab_length
        return screen.cursor.x

    tab_bg = screen.cursor.bg
    tab_fg = screen.cursor.fg
    default_bg = as_rgb(int(draw_data.default_bg))

    if max_title_length <= 3:
        screen.draw(' … ')
    else:
        screen.draw(' ')
        draw_title(draw_data, screen, tab, index, max_title_length - 2)
        screen.draw(' ')

    if is_last:
        # Should not happen as we compute tab width such that the tab bar gets
        # completely filled, but if anything weird happens we cover past the
        # last tab so that the bar's background doesn't show (esp. annoying if
        # the last tab is active).
        if (e := screen.columns - screen.cursor.x) > 0:
            screen.draw(' ' * e)
    elif sep_is_hard:
        screen.cursor.fg = tab_bg
        screen.cursor.bg = next_tab_bg
        screen.draw(sep)
    else:
        prev_fg = screen.cursor.fg
        if tab_bg == tab_fg:
            screen.cursor.fg = default_bg
        elif tab_bg != default_bg:
            c1 = draw_data.inactive_bg.contrast(draw_data.default_bg)
            c2 = draw_data.inactive_bg.contrast(draw_data.inactive_fg)
            if c1 < c2:
                screen.cursor.fg = default_bg
        screen.draw(sep)
        screen.cursor.fg = prev_fg

    return screen.cursor.x
