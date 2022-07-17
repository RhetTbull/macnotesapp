"""Custom param types for CLI"""

import click
import validators


class URLType(click.ParamType):
    """A valid URL"""

    name = "URL"

    def convert(self, value, param, ctx):
        if validators.url(value):
            return value
        else:
            self.fail(f"Invalid URL: '{value}'.")
