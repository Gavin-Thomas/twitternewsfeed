#!/usr/bin/env python3
"""CLI entry point for generating YouTube video outlines.

Usage:
    python generate_outline.py "Your video topic here"
    python generate_outline.py "Your topic" --url "https://source.com"
    python generate_outline.py "Your topic" --url "https://source.com" --score 7
    python generate_outline.py "Your topic" --summary "Extra context about the topic"
"""
import argparse
import sys

from src.outline import generate_outline, format_outline_markdown


def main() -> None:
    """Parse CLI arguments and print a formatted video outline to stdout."""
    parser = argparse.ArgumentParser(
        description="Generate a YouTube video outline from a topic.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python generate_outline.py "Claude Code MCP server launched"\n'
            '  python generate_outline.py "How to build a voice agent with Vapi" '
            '--url "https://vapi.ai"\n'
            '  python generate_outline.py "n8n open-source automation" '
            '--summary "New workflow engine" --score 8\n'
        ),
    )
    parser.add_argument(
        "topic",
        help="Article title or video idea to generate an outline for.",
    )
    parser.add_argument(
        "--url",
        default="",
        help="Source URL to include in the description.",
    )
    parser.add_argument(
        "--summary",
        default="",
        help="Optional summary text for richer keyword extraction.",
    )
    parser.add_argument(
        "--score",
        type=int,
        default=0,
        help="Relevance score (0-10) from the scoring pipeline.",
    )

    args = parser.parse_args()

    outline = generate_outline(
        topic=args.topic,
        summary=args.summary,
        source_url=args.url,
        score=args.score,
    )

    print(format_outline_markdown(outline))


if __name__ == "__main__":
    main()
