import inspect
import os

from steely.design import UnicodeColors, UnicodeColor


def pprint(*args, color: UnicodeColor = UnicodeColors.header, **kwargs):
    """
    Pretty print with caller location information.

    Prints the provided arguments along with the file and line number of the caller,
    formatted in a way that allows IDEs and terminals to create clickable links.

    Args:
        *args: Values to print
        **kwargs: Keyword arguments passed to the built-in print function
        :param color: Color definition for this print occurrence.
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

