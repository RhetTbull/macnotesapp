"""Custom param types for CLI"""

import click


class URLType(click.ParamType):
    """A valid URL"""

    name = "URL"

    def convert(self, value, param, ctx):
        import validators

        if validators.url(value):
            return value
        else:
            self.fail(f"Invalid URL: '{value}'.")
