"""
Design Module - Terminal Styling and Visual Elements
=====================================================

This module provides ANSI escape codes for terminal colors, text styles,
and Unicode symbols used throughout Steely for beautiful console output.

Classes
-------
UnicodeColors
    ANSI escape sequences for text colors and styles.
TypeColors
    Color mapping specifically designed for Python data types.
Symbols
    Unicode symbols for visual elements like arrows, boxes, and indicators.

Examples
--------
Using colors in terminal output:

>>> from steely.design import UnicodeColors as C
>>> print(f"{C.green}Success!{C.reset}")
>>> print(f"{C.bold}{C.red}Error!{C.reset}")

Using type-specific colors:

>>> from steely.design import TypeColors
>>> color = TypeColors.get_color(42)  # Returns blue for int
>>> print(f"{color}42{UnicodeColors.reset}")

Using symbols:

>>> from steely.design import Symbols as S
>>> print(f"{S.CHECK} Task completed")
>>> print(f"{S.ARROW_RIGHT} Next step")

Notes
-----
These colors use ANSI escape sequences which are supported by most modern
terminals. On Windows, you may need to enable ANSI support or use a
compatible terminal emulator.
"""

__all__ = ["UnicodeColors", "TypeColors", "Symbols"]


class UnicodeColors:
    """
    ANSI escape sequences for terminal text styling.

    This class provides a comprehensive collection of ANSI color codes
    for styling terminal output. Colors are organized into categories:
    semantic colors, basic colors, bright colors, and background colors.

    Attributes
    ----------
    Semantic Colors (for log levels):
        header : str
            Purple/magenta for headers (\\033[95m)
        success_blue : str
            Blue for informational success (\\033[94m)
        success_cyan : str
            Cyan for start/info messages (\\033[96m)
        success : str
            Green for success messages (\\033[92m)
        alert : str
            Yellow for warnings (\\033[93m)
        fail : str
            Red for errors and failures (\\033[91m)

    Text Styles:
        bold : str
            Bold text (\\033[1m)
        dim : str
            Dimmed/faint text (\\033[2m)
        italic : str
            Italic text (\\033[3m)
        underline : str
            Underlined text (\\033[4m)
        reset : str
            Reset all styles (\\033[0m)
        endc : str
            Alias for reset (\\033[0m)

    Basic Colors (30-37):
        black, red, green, yellow, blue, purple, cyan, white

    Extended Colors (256-color mode):
        orange, pink, teal, brown, lavender, indigo, maroon, olive, steel_blue

    Bright Colors (90-97):
        bright_black, bright_red, bright_green, bright_yellow,
        bright_blue, bright_purple, bright_cyan, bright_white

    Background Colors (40-47):
        bg_black, bg_red, bg_green, bg_yellow,
        bg_blue, bg_purple, bg_cyan, bg_white

    Examples
    --------
    >>> from steely.design import UnicodeColors as C
    >>> print(f"{C.bold}{C.green}Bold green text{C.reset}")
    >>> print(f"{C.bg_blue}{C.white}White on blue{C.reset}")
    >>> print(f"{C.orange}Extended color{C.reset}")
    """

    # Semantic colors for logging
    header = '\033[95m'
    success_blue = '\033[94m'
    success_cyan = '\033[96m'
    success = '\033[92m'
    alert = '\033[93m'
    fail = '\033[91m'
    endc = '\033[0m'
    bold = '\033[1m'
    underline = '\033[4m'
    reset = '\033[0m'
    dim = '\033[2m'
    italic = '\033[3m'

    # Basic Rainbow Colors (Standard 8 colors)
    black = '\033[30m'
    red = '\033[31m'
    green = '\033[32m'
    yellow = '\033[33m'
    blue = '\033[34m'
    purple = '\033[35m'
    cyan = '\033[36m'
    white = '\033[37m'

    # Extended Colors (256-color palette)
    orange = '\033[38;5;208m'
    pink = '\033[38;5;206m'
    teal = '\033[38;5;39m'
    brown = '\033[38;5;130m'
    lavender = '\033[38;5;183m'
    indigo = '\033[38;5;62m'
    maroon = '\033[38;5;52m'
    olive = '\033[38;5;100m'
    steel_blue = '\033[38;5;67m'

    # Bright Rainbow Colors (High intensity)
    bright_black = '\033[90m'
    bright_red = '\033[91m'
    bright_green = '\033[92m'
    bright_yellow = '\033[93m'
    bright_blue = '\033[94m'
    bright_purple = '\033[95m'
    bright_cyan = '\033[96m'
    bright_white = '\033[97m'

    # Background Colors
    bg_black = '\033[40m'
    bg_red = '\033[41m'
    bg_green = '\033[42m'
    bg_yellow = '\033[43m'
    bg_blue = '\033[44m'
    bg_purple = '\033[45m'
    bg_cyan = '\033[46m'
    bg_white = '\033[47m'


class TypeColors:
    """
    ANSI color codes mapped to Python data types.

    This class provides a consistent color scheme for visualizing different
    Python types in terminal output. Each type has a distinct, carefully
    chosen color for easy visual differentiation.

    Attributes
    ----------
    INT : str
        Bright blue (\\033[38;5;39m) - For integer values
    FLOAT : str
        Deep blue (\\033[38;5;33m) - For floating-point numbers
    STR : str
        Orange (\\033[38;5;208m) - For string values
    BOOL : str
        Magenta (\\033[38;5;164m) - For boolean values
    NONE : str
        Gray (\\033[38;5;245m) - For None values
    LIST : str
        Sea green (\\033[38;5;78m) - For list objects
    DICT : str
        Gold (\\033[38;5;220m) - For dictionary objects
    TUPLE : str
        Light purple (\\033[38;5;141m) - For tuple objects
    SET : str
        Pink (\\033[38;5;204m) - For set objects
    CALLABLE : str
        Cyan (\\033[38;5;123m) - For functions and callables
    CLASS : str
        Lavender (\\033[38;5;183m) - For class instances
    DEFAULT : str
        Light gray (\\033[38;5;252m) - Fallback color

    Methods
    -------
    get_color(value)
        Returns the appropriate color code for a given value.

    Examples
    --------
    >>> from steely.design import TypeColors, UnicodeColors
    >>> value = [1, 2, 3]
    >>> color = TypeColors.get_color(value)
    >>> print(f"{color}{value}{UnicodeColors.reset}")  # Prints in sea green
    """

    INT = '\033[38;5;39m'
    FLOAT = '\033[38;5;33m'
    STR = '\033[38;5;208m'
    BOOL = '\033[38;5;164m'
    NONE = '\033[38;5;245m'
    LIST = '\033[38;5;78m'
    DICT = '\033[38;5;220m'
    TUPLE = '\033[38;5;141m'
    SET = '\033[38;5;204m'
    CALLABLE = '\033[38;5;123m'
    CLASS = '\033[38;5;183m'
    DEFAULT = '\033[38;5;252m'

    @classmethod
    def get_color(cls, value):
        """
        Get the appropriate ANSI color code for a value based on its type.

        This method inspects the type of the given value and returns the
        corresponding color code from the TypeColors class.

        Parameters
        ----------
        value : Any
            The value to get a color for. Can be any Python object.

        Returns
        -------
        str
            ANSI escape sequence for the appropriate color.

        Notes
        -----
        - Boolean is checked before int because bool is a subclass of int
        - Callable check comes after specific types to avoid false positives
        - Unknown types default to CLASS color (lavender)

        Examples
        --------
        >>> TypeColors.get_color(42)
        '\\033[38;5;39m'  # Blue for int
        >>> TypeColors.get_color("hello")
        '\\033[38;5;208m'  # Orange for str
        >>> TypeColors.get_color(None)
        '\\033[38;5;245m'  # Gray for None
        """
        if value is None:
            return cls.NONE
        elif isinstance(value, bool):
            return cls.BOOL
        elif isinstance(value, int):
            return cls.INT
        elif isinstance(value, float):
            return cls.FLOAT
        elif isinstance(value, str):
            return cls.STR
        elif isinstance(value, list):
            return cls.LIST
        elif isinstance(value, dict):
            return cls.DICT
        elif isinstance(value, tuple):
            return cls.TUPLE
        elif isinstance(value, set):
            return cls.SET
        elif callable(value):
            return cls.CALLABLE
        else:
            return cls.CLASS


class Symbols:
    """
    Unicode symbols for beautiful terminal output.

    This class provides a collection of Unicode characters commonly used
    for creating visually appealing terminal interfaces, including arrows,
    box-drawing characters, and indicator symbols.

    Attributes
    ----------
    Arrows:
        ARROW_RIGHT : str
            Right arrow (→)
        ARROW_LEFT : str
            Left arrow (←)
        ARROW_UP : str
            Up arrow (↑)
        ARROW_DOWN : str
            Down arrow (↓)
        RETURN : str
            Return/map arrow (⟼)

    Status Indicators:
        CHECK : str
            Checkmark (✓) - Success indicator
        CROSS : str
            Cross mark (✗) - Failure indicator
        STAR : str
            Star (★)
        BULLET : str
            Bullet point (•)

    Shapes:
        DIAMOND : str
            Diamond (◆)
        CIRCLE : str
            Filled circle (●)
        SQUARE : str
            Filled square (■)
        TRIANGLE : str
            Triangle (▲)

    Box Drawing:
        BOX_H : str
            Horizontal line (─)
        BOX_V : str
            Vertical line (│)
        BOX_TL : str
            Top-left corner (┌)
        BOX_TR : str
            Top-right corner (┐)
        BOX_BL : str
            Bottom-left corner (└)
        BOX_BR : str
            Bottom-right corner (┘)
        BOX_T : str
            T-junction top (┬)
        BOX_B : str
            T-junction bottom (┴)
        BOX_L : str
            T-junction left (├)
        BOX_R : str
            T-junction right (┤)
        BOX_X : str
            Cross junction (┼)

    Special:
        ELLIPSIS : str
            Ellipsis (…) - For truncated text
        SCAN : str
            Lightning bolt (⚡) - Scan indicator
        VAR : str
            Variable marker (◈)
        TYPE : str
            Type marker (◉)
        LINE : str
            Line indicator (▸)

    Examples
    --------
    Creating a simple box:

    >>> from steely.design import Symbols as S
    >>> print(f"{S.BOX_TL}{S.BOX_H * 10}{S.BOX_TR}")
    >>> print(f"{S.BOX_V}  Hello   {S.BOX_V}")
    >>> print(f"{S.BOX_BL}{S.BOX_H * 10}{S.BOX_BR}")

    Status messages:

    >>> print(f"{S.CHECK} Task completed successfully")
    >>> print(f"{S.CROSS} Task failed")
    >>> print(f"{S.ARROW_RIGHT} Processing next item")
    """

    # Arrows
    ARROW_RIGHT = '→'
    ARROW_LEFT = '←'
    ARROW_UP = '↑'
    ARROW_DOWN = '↓'

    # Status indicators
    CHECK = '✓'
    CROSS = '✗'
    STAR = '★'
    BULLET = '•'

    # Shapes
    DIAMOND = '◆'
    CIRCLE = '●'
    SQUARE = '■'
    TRIANGLE = '▲'

    # Box drawing characters
    BOX_H = '─'
    BOX_V = '│'
    BOX_TL = '┌'
    BOX_TR = '┐'
    BOX_BL = '└'
    BOX_BR = '┘'
    BOX_T = '┬'
    BOX_B = '┴'
    BOX_L = '├'
    BOX_R = '┤'
    BOX_X = '┼'

    # Special symbols
    ELLIPSIS = '…'
    SCAN = '⚡'
    VAR = '◈'
    TYPE = '◉'
    LINE = '▸'
    RETURN = '⟼'
