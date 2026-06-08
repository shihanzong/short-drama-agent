#!/usr/bin/env python3
"""Short Drama Agent - Main Entry Point.

Usage:
    python main.py --genre "重生复仇" --episodes 5
    python main.py --genre "霸总" --episodes 3 --style anime
    python main.py --genre "逆袭" --episodes 5 --mode quick
"""

import argparse
import os
import sys

from workflow import ShortDramaWorkflow


def main():
    parser = argparse.ArgumentParser(
        description="Short Drama Agent - AI-powered short drama production pipeline"
    )
    parser.add_argument(
        "--genre", "-g",
        type=str,
        default="重生复仇",
        help="Drama genre (default: 重生复仇). Options: 重生复仇, 霸总, 逆袭, 悬疑, 战神, 甜宠",
    )
    parser.add_argument(
        "--episodes", "-e",
        type=int,
        default=3,
        help="Number of episodes to produce (default: 3)",
    )
    parser.add_argument(
        "--style", "-s",
        type=str,
        default="cinematic_realistic",
        help="Visual style (default: cinematic_realistic). Options: cinematic_realistic, anime, noir, webtoon",
    )
    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["full", "quick", "planning-only"],
        default="full",
        help="Production mode (default: full). quick skips visual/audio, planning-only stops after planning.",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to config.yaml (default: project config.yaml)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="output",
        help="Output base directory (default: output)",
    )
    parser.add_argument(
        "--list-genres",
        action="store_true",
        help="List available genres and exit",
    )

    args = parser.parse_args()

    if args.list_genres:
        print("Available genres:")
        from agents.creative_planner import CreativePlannerAgent
        for name, info in CreativePlannerAgent.GENRE_TEMPLATES.items():
            print(f"  {name}: {info['description']}")
        return

    print("=" * 50)
    print("  Short Drama Agent v1.0")
    print("  AI短剧一条龙生产系统")
    print("=" * 50)

    # Initialize workflow
    workflow = ShortDramaWorkflow(config_path=args.config)

    # Quick mode: skip visual/audio
    skip_visual = args.mode in ("quick", "planning-only")
    skip_publish = args.mode == "planning-only"

    if args.mode == "planning-only":
        print("\nPlanning-only mode: generating creative plan only...")
        planning = workflow.creative_planner.run(args.genre, args.episodes)
        print(f"\nGenre: {args.genre}")
        print(f"Character cards: {len(planning.get('character_cards', []))}")
        print(f"Episode outlines: {len(planning.get('episode_outlines', []))}")
        return

    # Run full series
    result = workflow.run_series(
        genre=args.genre,
        episode_count=args.episodes,
        style=args.style,
        output_base=args.output,
        quick_mode=(args.mode == "quick"),
    )

    print(f"\nDone! Output: {result['output_directory']}")


if __name__ == "__main__":
    main()
