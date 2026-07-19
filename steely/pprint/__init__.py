import inspect
import os

from steely.design import UnicodeColors, UnicodeColor


def pprint(*args, color: UnicodeColor = UnicodeColors.header, **kwargs):
    """Print with a clickable caller ``file:line`` location header.

    A drop-in replacement for :func:`print` that, before your output, emits the
    absolute path and line number of the call site — formatted so most IDEs and
    terminals turn it into a clickable link. Ideal for quick, easy-to-locate
    debug statements without setting up a full logger.

    Parameters
    ----------
    *args :
        Values to print, exactly as you would pass them to the built-in
        :func:`print`.
    color : UnicodeColor, optional
        Color of the ``[PPRINT] File ...`` location header. Defaults to
        :data:`steely.design.UnicodeColors.header`. Pick from
        :class:`steely.design.UnicodeColors` (e.g. ``.success``, ``.fail``,
        ``.alert``). Only the header is colored; your values print normally.
    **kwargs :
        Forwarded verbatim to the built-in :func:`print` (``sep``, ``end``,
        ``file``, ``flush``).

    Examples
    --------
    >>> from steely.pprint import pprint
    >>> pprint("Subtotal:", 60)
    [PPRINT] File "/path/to/script.py", line 12
    Subtotal: 60

    >>> from steely.design import UnicodeColors
    >>> pprint("Something went wrong!", color=UnicodeColors.fail)
    """
    # Get the caller's frame
    frame = inspect.currentframe()
    if frame is not None:
        caller_frame = frame.f_back
        if caller_frame is not None:
            # Get caller information
            filename = caller_frame.f_code.co_filename
            lineno = caller_frame.f_lineno

            # Convert to absolute path if relative
            filename = os.path.abspath(filename)

            # Format the location in a clickable format
            location = f'\n{UnicodeColors.bold}{color}[PPRINT] File "{filename}", line {lineno}'

            # Print the location first
            print(location)

            # Print the actual content
            print(*args, **kwargs)
        else:
            # Fallback if we can't get caller frame
            print(*args, **kwargs)
    else:
        # Fallback if inspect doesn't work
        print(*args, **kwargs)

    print(UnicodeColors.reset)

__all__ = ['pprint']

