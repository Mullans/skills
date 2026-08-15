"""Command-line interface for mark2word."""

from __future__ import annotations

import argparse
import sys
import warnings
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from mark2word.emit import build
from mark2word.errors import Mark2WordError
from mark2word.parser import parse_to_ast
from mark2word.paths import (
    ensure_input_readable,
    ensure_output_writable,
    raise_if_output_write_blocked,
)
from mark2word.theme import (
    discover_theme_dirs,
    ensure_theme_chain_readable,
    load_theme,
    split_frontmatter,
)
from mark2word.theme_validate import validate_theme_file

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2


class UsageError(Mark2WordError):
    """Invalid CLI invocation (maps to exit code 2)."""


def validate_theme(theme_path: Path, theme_dirs: list[Path]) -> None:
    validate_theme_file(theme_path, theme_dirs=theme_dirs)
    print(f"OK {theme_path}")


def _package_version() -> str:
    try:
        return version("mark2word")
    except PackageNotFoundError:
        return "0.1.0"


def validate_document(md_path: Path, theme_dirs: list[Path]) -> None:
    ensure_input_readable(md_path, kind="input")
    text = md_path.read_text(encoding="utf-8")
    front, body = split_frontmatter(text)
    ensure_theme_chain_readable(front, md_path, theme_dirs=theme_dirs)
    parse_to_ast(body)


def _is_explicit_output_file(path: Path) -> bool:
    if path.exists():
        return path.is_file()
    return path.suffix.lower() == ".docx"


def resolve_output_path(
    md_path: Path,
    output: Path | None,
    *,
    multiple_inputs: bool,
) -> Path:
    """Resolve the .docx path for a single markdown input."""
    if multiple_inputs:
        if output is None:
            return md_path.with_suffix(".docx")
        if _is_explicit_output_file(output):
            raise UsageError(
                f"--output must be a directory when converting multiple inputs: {output}"
            )
        output.mkdir(parents=True, exist_ok=True)
        return output / f"{md_path.stem}.docx"

    if output is None:
        return md_path.with_suffix(".docx")
    if _is_explicit_output_file(output):
        output.parent.mkdir(parents=True, exist_ok=True)
        return output
    output.mkdir(parents=True, exist_ok=True)
    return output / f"{md_path.stem}.docx"


def convert_one(
    md_path: Path,
    out_path: Path,
    theme_dirs: list[Path],
    *,
    check: bool = False,
    verbose: bool = False,
) -> None:
    ensure_input_readable(md_path, kind="input")
    if not check:
        ensure_output_writable(out_path)
    text = md_path.read_text(encoding="utf-8")
    front, body = split_frontmatter(text)
    ensure_theme_chain_readable(front, md_path, theme_dirs=theme_dirs)
    if check:
        parse_to_ast(body)
        print(f"OK {md_path}")
        return
    external, glob = load_theme(front, md_path, theme_dirs=theme_dirs)
    try:
        build(glob, external, body, out_path, verbose=verbose, md_path=md_path)
    except (PermissionError, OSError) as exc:
        raise_if_output_write_blocked(out_path, exc)


def _collect_inputs(args: argparse.Namespace) -> list[Path]:
    inputs = list(args.inputs or [])
    inputs.extend(args.positional_inputs or [])
    if not inputs:
        raise UsageError("at least one input file is required (use -i/--input)")
    return inputs


def _prepare_jobs(args: argparse.Namespace) -> list[tuple[Path, Path, list[Path]]]:
    input_files = _collect_inputs(args)
    multiple = len(input_files) > 1
    jobs: list[tuple[Path, Path, list[Path]]] = []

    for md_path in input_files:
        ensure_input_readable(md_path, kind="input")
        theme_dirs = list(args.theme_dir)
        if not args.no_auto_theme_dir:
            for discovered in discover_theme_dirs(md_path):
                if discovered not in theme_dirs:
                    theme_dirs.append(discovered)
        out_path = resolve_output_path(md_path, args.output, multiple_inputs=multiple)
        text = md_path.read_text(encoding="utf-8")
        front, _ = split_frontmatter(text)
        ensure_theme_chain_readable(front, md_path, theme_dirs=theme_dirs)
        jobs.append((md_path, out_path, theme_dirs))

    if not args.check:
        for _, out_path, _ in jobs:
            ensure_output_writable(out_path)

    return jobs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert a styled-Markdown dialect into a Word document."
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="inputs",
        action="append",
        type=Path,
        help="Markdown input file. Repeat for multiple files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "Output .docx file or directory. With one input, may be an explicit "
            ".docx path or a directory (uses the markdown basename). With multiple "
            "inputs, must be a directory."
        ),
    )
    parser.add_argument(
        "--theme-dir",
        action="append",
        default=[],
        type=Path,
        help="Additional folder to search for relative frontmatter extends paths.",
    )
    parser.add_argument(
        "--no-auto-theme-dir",
        action="store_true",
        help="Do not search .mark2word/themes near the input file.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate frontmatter, theme, and markdown without writing a .docx.",
    )
    parser.add_argument(
        "--check-theme",
        type=Path,
        metavar="THEME",
        help="Validate a theme YAML file (including extends chain) without converting.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit warnings such as ignored ordered-list numbers.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"mark2word {_package_version()}",
    )
    parser.add_argument(
        "positional_inputs",
        nargs="*",
        type=Path,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    if args.verbose:
        warnings.simplefilter("always")

    if args.check_theme is not None:
        try:
            validate_theme(args.check_theme, list(args.theme_dir))
        except Mark2WordError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_FAILURE
        return EXIT_SUCCESS

    try:
        jobs = _prepare_jobs(args)
    except UsageError as exc:
        parser.error(str(exc))
    except Mark2WordError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FAILURE

    for md_path, out_path, theme_dirs in jobs:
        try:
            convert_one(
                md_path,
                out_path,
                theme_dirs,
                check=args.check,
                verbose=args.verbose,
            )
        except Mark2WordError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_FAILURE

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
