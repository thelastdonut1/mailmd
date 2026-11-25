"""Command-line interface."""

import os
from pathlib import Path
from typing import Annotated

import typer

from mailmd.convert import OutputExistsError, PathTooLongError, plan, write
from mailmd.naming import is_valid_folder_name

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
        typer.Option("--out", "-o", file_okay=False, help="Where to create thread folders. Default: current folder."),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Name for the thread folder, used exactly as given. Single file only."),
    ] = None,
    no_source: Annotated[
        bool, typer.Option("--no-source", help="Don't copy the original .eml into the thread folder.")
    ] = False,
    force: Annotated[bool, typer.Option("--force", help="Replace a thread folder that already exists.")] = False,
) -> None:
    """Write one folder per .eml file: Markdown, attachments/ and a copy of the original as source.eml."""
    if name is not None:
        if len(files) > 1:
            raise typer.BadParameter("--name can only be used when converting a single file", param_hint="--name")
        if not is_valid_folder_name(name):
            raise typer.BadParameter(f"{name!r} is not a valid folder name", param_hint="--name")

    parent = out or Path.cwd()
    written: set[str] = set()
    failed = False
    for path in files:
        if path.suffix.lower() != ".eml":
            typer.echo(f"Skipping {path.name}: only .eml files are supported", err=True)
            continue
        try:
            planned = plan(path, parent, name=name, include_source=not no_source)
            if planned.folder.name.lower() in written:
                # Two inputs from the same day with the same subject; never let the second replace the first.
                raise OutputExistsError(f"{planned.folder.name} was already written in this run")
            result = write(planned, force=force)
        except (OutputExistsError, PathTooLongError) as error:
            typer.echo(f"Skipping {path.name}: {error}", err=True)
            failed = True
            continue
        written.add(result.folder.name.lower())
        attachments = f", {len(result.attachment_paths)} attachment(s)" if result.attachment_paths else ""
        typer.echo(f"Wrote {result.folder}{os.sep} ({result.message_count} messages{attachments})")
    if failed:
        raise typer.Exit(code=1)
