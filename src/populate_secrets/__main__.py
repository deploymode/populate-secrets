#!/usr/bin/env python
"""The main entry point. Invoke as `populate-secrets`
"""


def main():
    from .cli import cli

    cli()


if __name__ == "__main__":
    main()
