"""Help text helper class for macnotesapp CLI """

import inspect
import re
import typing as t

import click
from rich.console import Console
from rich.markdown import Markdown

from .click_rich_echo import rich_echo_via_pager, set_rich_console

HELP_WIDTH = 110
HIGHLIGHT_COLOR = "yellow"

__all__ = [
    "ExportCommand",
    "template_help",
    "rich_text",
    "strip_md_header_and_links",
    "strip_md_links",
    "strip_html_comments",
    "help",
    "get_help_msg",
]


def get_help_msg(command):
    """get help message for a Click command"""
    with click.Context(command) as ctx:
        return command.get_help(ctx)


class RichHelpCommand(click.Command):
    """Custom click.Command that overrides get_help() to print rich help text"""

    def get_help(self, ctx):
        """Get help with rich markup"""
        help_text = super().get_help(ctx)
        formatter = click.HelpFormatter(width=HELP_WIDTH)
        formatter.write(rich_text(help_text, width=HELP_WIDTH))
        return formatter.getvalue()

    def get_help_no_markup(self, ctx):
        """Get help without any rich markup"""
        help_text = super().get_help(ctx)
        formatter = click.HelpFormatter(width=HELP_WIDTH)
        formatter.write(rich_text(help_text, width=HELP_WIDTH, markup=False))
        return formatter.getvalue()


@click.command()
@click.option(
    "--width",
    default=HELP_WIDTH,
    help="Width of help text",
    hidden=True,
)
@click.option(
    "--no-markup", is_flag=True, help="Print output with no markup", hidden=True
)
@click.argument("topic", default=None, required=False, nargs=1)
@click.argument("subtopic", default=None, required=False, nargs=1)
@click.pass_context
def help(ctx, topic, subtopic, width, no_markup, **kw):
    """Print help; for help on commands: help <command>."""
    if topic is None:
        click.echo(ctx.parent.get_help())
        return

    global HELP_WIDTH
    HELP_WIDTH = width

    wrap_text_original = click.formatting.wrap_text

    def wrap_text(
        text: str,
        width: int = HELP_WIDTH,
        initial_indent: str = "",
        subsequent_indent: str = "",
        preserve_paragraphs: bool = False,
    ) -> str:
        return wrap_text_original(
            text,
            width=width,
            initial_indent=initial_indent,
            subsequent_indent=subsequent_indent,
            preserve_paragraphs=preserve_paragraphs,
        )

    click.formatting.wrap_text = wrap_text
    click.wrap_text = wrap_text

    if subtopic:
        cmd = ctx.obj.group.commands[topic]
        help_text = get_subtopic_help(cmd, ctx, subtopic)
        rich_echo_via_pager(
            help_text,
            # theme=get_theme(),
            width=HELP_WIDTH,
            color=not no_markup,
        )
        return

    if topic in ctx.obj.group.commands:
        ctx.info_name = topic
        # click.echo_via_pager(ctx.obj.group.commands[topic].get_help(ctx))
        try:
            help_text = (
                ctx.obj.group.commands[topic].get_help_no_markup(ctx)
                if no_markup
                else ctx.obj.group.commands[topic].get_help(ctx)
            )
        except AttributeError:
            # Not a RichHelpCommand
            help_text = ctx.obj.group.commands[topic].get_help(ctx)

        rich_echo_via_pager(
            help_text,
            width=HELP_WIDTH,
            color=not no_markup,
        )
        return

    # didn't find any valid help topics
    click.echo(f"Invalid command: {topic}", err=True)
    click.echo(ctx.parent.get_help())


def get_subtopic_help(cmd: click.Command, ctx: click.Context, subtopic: str):
    """Get help for a command including only options that match a subtopic"""

    # set ctx.info_name or click prints the wrong usage str (usage for help instead of cmd)
    ctx.info_name = cmd.name
    usage_str = cmd.get_help(ctx)
    usage_str = usage_str.partition("\n")[0]

    info = cmd.to_info_dict(ctx)
    help_str = info.get("help", "")

    options = get_matching_options(cmd, ctx, subtopic)

    # format help text and options
    formatter = click.HelpFormatter(width=HELP_WIDTH)
    formatter.write(usage_str)
    formatter.write_paragraph()
    format_help_text(help_str, formatter)
    formatter.write_paragraph()
    if options:
        option_str = format_options_help(options, ctx, highlight=subtopic)
        formatter.write(f"Options that match '[highlight]{subtopic}[/highlight]':\n")
        formatter.write_paragraph()
        formatter.write(option_str)
    else:
        formatter.write(f"No options match '[highlight]{subtopic}[/highlight]'")
    return formatter.getvalue()


def get_matching_options(
    command: click.Command, ctx: click.Context, topic: str
) -> t.List:
    """Get matching options for a command that contain a topic

    Args:
        command: click.Command
        ctx: click.Context
        topic: str, topic to match

    Returns:
        list of matching click.Option objects

    """
    options = []
    topic = topic.lower()
    for option in command.params:
        help_record = option.get_help_record(ctx)
        if help_record and (topic in help_record[0] or topic in help_record[1]):
            options.append(option)
    return options


def format_options_help(
    options: t.List[click.Option], ctx: click.Context, highlight: t.Optional[str] = None
) -> str:
    """Format options help for display

    Args:
        options: list of click.Option objects
        ctx: click.Context
        highlight: str, if set, add rich highlighting to options that match highlight str

    Returns:
        str with formatted help

    """
    formatter = click.HelpFormatter(width=HELP_WIDTH)
    opt_help = [opt.get_help_record(ctx) for opt in options]
    if highlight:
        # convert list of tuples to list of lists
        opt_help = [list(opt) for opt in opt_help]
        for record in opt_help:
            record[0] = re.sub(
                f"({highlight})",
                "[highlight]\\1[/highlight]",
                record[0],
                re.IGNORECASE,
            )

            record[1] = re.sub(
                f"({highlight})",
                "[highlight]\\1[/highlight]",
                record[1],
                re.IGNORECASE,
            )

        # convert back to list of tuples as that's what write_dl expects
        opt_help = [tuple(opt) for opt in opt_help]
    formatter.write_dl(opt_help)
    return formatter.getvalue()


def format_help_text(text: str, formatter: click.HelpFormatter):
    text = inspect.cleandoc(text).partition("\f")[0]
    formatter.write_paragraph()

    with formatter.indentation():
        formatter.write_text(text)


def rich_text(text: str, width: int = 78, markdown: bool = False, markup: bool = True):
    """Return rich formatted text

    Args:
        text: text to format
        width: default terminal width
        markdown: if True, uses markdown syntax for formatting text
        markup: if False, does not use rich markup
    """
    console = Console(force_terminal=markup, width=width)
    with console.capture() as capture:
        console.print(Markdown(text) if markdown else text, end="")
    return capture.get()


def strip_md_header_and_links(md):
    """strip markdown headers and links from markdown text md

    Args:
        md: str, markdown text

    Returns:
        str with markdown headers and links removed

    Note: This uses a very basic regex that likely fails on all sorts of edge cases
    but works for the links in the osxphotos docs
    """
    links = r"(?:[*#])|\[(.*?)\]\(.+?\)"

    def subfn(match):
        return match.group(1)

    return re.sub(links, subfn, md)


def strip_md_links(md):
    """strip markdown links from markdown text md

    Args:
        md: str, markdown text

    Returns:
        str with markdown links removed

    Note: This uses a very basic regex that likely fails on all sorts of edge cases
    but works for the links in the osxphotos docs
    """
    links = r"\[(.*?)\]\(.+?\)"

    def subfn(match):
        return match.group(1)

    return re.sub(links, subfn, md)


def strip_html_comments(text):
    """Strip html comments from text (which doesn't need to be valid HTML)"""
    return re.sub(r"<!--(.|\s|\n)*?-->", "", text)
