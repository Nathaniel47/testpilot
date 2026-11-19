import argparse

from testpilot import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="testpilot",
        description="Generate unit tests with an LLM and grade them by mutation score.",
    )
    parser.add_argument("--version", action="version", version=f"testpilot {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
