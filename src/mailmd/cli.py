"""Command-line interface."""

from pathlib import Path
from typing import Annotated

import typer

from mailmd.convert import convert as convert_file

app = typer.Typer(help="Convert exported Outlook email threads (.eml) into clean Markdown.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Keep `convert` as an explicit subcommand so more commands can be added later."""


@app.command()
def convert(
    files: Annotated[
        list[Path],
        typer.Argument(exists=True, dir_okay=False, readable=True, help=".eml files to convert, each on its own."),
    ],
    out: Annotated[
        Path | None,
        typer.Option("--out", "-o", file_okay=False, help="Output folder. Defaults to each file's own folder."),
    ] = None,
) -> None:
    """Write FILE.md (and FILE_attachments/ when there are attachments) for each .eml file."""
    for path in files:
        if path.suffix.lower() != ".eml":
            typer.echo(f"Skipping {path.name}: only .eml files are supported", err=True)
            continue
        result = convert_file(path, out)
        attachments = f", {len(result.attachment_paths)} attachment(s)" if result.attachment_paths else ""
        typer.echo(f"Wrote {result.markdown_path} ({result.message_count} messages{attachments})")
