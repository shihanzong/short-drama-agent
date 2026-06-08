#!/usr/bin/env python3
"""Batch Generator - Produce multiple drama series in one run.

Usage:
    python batch_generate.py --genres "重生复仇,霸总,逆袭" --episodes 5
    python batch_generate.py --all --episodes 3 --style cinematic_realistic
    python batch_generate.py --file genres_list.txt  # one genre per line
    python batch_generate.py --genres "重生复仇" --episodes 10 --output my_dramas

Output structure:
    my_dramas/
        重生复仇/
            ep001/
                script.md
                outline.json
                result.json
            ep002/
                ...
            planning.json
            overall_result.json
            analytics.json
        霸总/
            ...
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow import ShortDramaWorkflow
from modules.analytics import AnalyticsEngine
from agents.creative_planner import CreativePlannerAgent


def list_available_genres():
    """Print all available genres."""
    print("Available genres:")
    for name, info in CreativePlannerAgent.GENRE_TEMPLATES.items():
        print(f"  {name:12s} - {info['description']}")
        print(f"  {'':12s}  关键元素: {', '.join(info['key_elements'])}")
        print(f"  {'':12s}  目标受众: {info['target_audience']}")
        print()


def load_genres_from_file(filepath: str) -> list:
    """Load genre names from a text file, one per line."""
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def generate_analytics(
    results: list,
    output_dir: str,
    total_start: float,
):
    """Generate aggregate analytics after batch production."""
    total_episodes = sum(r.get("episodes_produced", 0) for r in results)
    total_time = time.time() - total_start

    analytics = {
        "generated_at": datetime.now().isoformat(),
        "total_series": len(results),
        "total_episodes": total_episodes,
        "total_production_time_seconds": round(total_time, 1),
        "avg_seconds_per_episode": round(total_time / max(total_episodes, 1), 1),
        "series": [],
    }

    for r in results:
        genre = r.get("genre", "unknown")
        eps = r.get("episodes_produced", 0)
        out_dir = r.get("output_directory", "")
        analytics["series"].append({
            "genre": genre,
            "episodes_produced": eps,
            "output_directory": out_dir,
            "quick_mode": True,  # batch always uses quick mode
        })

    analytics_path = os.path.join(output_dir, "analytics.json")
    with open(analytics_path, "w", encoding="utf-8") as f:
        json.dump(analytics, f, indent=2, ensure_ascii=False, default=str)

    return analytics


def batch_run(
    genres: list,
    episodes_per_genre: int,
    style: str,
    output_base: str,
    dry_run: bool = False,
):
    """Run production for multiple genres sequentially.

    Args:
        genres: List of genre names.
        episodes_per_genre: Episodes per genre.
        style: Visual style preset.
        output_base: Base output directory.
        dry_run: If True, only plan (no LLM calls).
    """
    total_start = time.time()
    results = []
    all_analytics = {"batch_start": datetime.now().isoformat()}

    for idx, genre in enumerate(genres):
        print("\n" + "=" * 60)
        print(f"  BATCH PROGRESS: [{idx+1}/{len(genres)}] Generating: {genre}")
        print("=" * 60)

        try:
            workflow = ShortDramaWorkflow()

            if dry_run:
                print(f"\n  [DRY RUN] Planning only for {genre}...")
                planning = workflow.creative_planner.run(genre, episodes_per_genre)
                result = {
                    "genre": genre,
                    "episodes_produced": len(planning.get("episode_outlines", [])),
                    "episodes": [
                        {"episode": i+1, "title": o.get("title", ""), "outline": o}
                        for i, o in enumerate(planning.get("episode_outlines", []))
                    ],
                    "output_directory": "",
                    "mode": "planning-only",
                    "planning": planning,
                }
            else:
                result = workflow.run_series(
                    genre=genre,
                    episode_count=episodes_per_genre,
                    style=style,
                    output_base=output_base,
                    quick_mode=True,
                )

            results.append(result)
            print(f"\n  [{genre}] DONE - Output: {result.get('output_directory', 'N/A')}")

        except Exception as e:
            print(f"\n  [{genre}] FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "genre": genre,
                "episodes_produced": 0,
                "output_directory": "",
                "error": str(e),
            })

        # Brief pause between genres to avoid API rate limits
        if idx < len(genres) - 1 and not dry_run:
            print("\n  Waiting 3s before next genre (rate limit)...")
            time.sleep(3)

    # Generate batch analytics
    analytics = generate_analytics(results, output_base, total_start)

    # Print summary
    print("\n" + "=" * 60)
    print("  BATCH PRODUCTION COMPLETE")
    print("=" * 60)
    print(f"  Total series: {analytics['total_series']}")
    print(f"  Total episodes: {analytics['total_episodes']}")
    print(f"  Total time: {analytics['total_production_time_seconds']}s")
    print(f"  Avg per episode: {analytics['avg_seconds_per_episode']}s")
    print()

    for s in analytics["series"]:
        status = "OK" if s["episodes_produced"] > 0 else "FAILED"
        print(f"  [{status}] {s['genre']:15s} - {s['episodes_produced']} eps")

    print(f"\n  Analytics: {os.path.join(output_base, 'analytics.json')}")

    return results, analytics


def main():
    parser = argparse.ArgumentParser(
        description="Batch generate multiple short drama series"
    )
    parser.add_argument(
        "--genres", "-g",
        type=str,
        default="重生复仇",
        help='Comma-separated genres (default: "重生复仇")',
    )
    parser.add_argument(
        "--episodes", "-e",
        type=int,
        default=3,
        help="Episodes per genre (default: 3)",
    )
    parser.add_argument(
        "--style", "-s",
        type=str,
        default="cinematic_realistic",
        help="Visual style preset",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="output",
        help="Base output directory",
    )
    parser.add_argument(
        "--list-genres",
        action="store_true",
        help="List available genres and exit",
    )
    parser.add_argument(
        "--from-file",
        type=str,
        help="Load genres from a text file (one per line)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all available genres",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Planning only, no LLM calls",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to config.yaml",
    )

    args = parser.parse_args()

    # Load genres
    if args.list_genres:
        list_available_genres()
        return

    if args.from_file:
        genres = load_genres_from_file(args.from_file)
        print(f"Loaded {len(genres)} genres from file: {args.from_file}")
    elif args.all:
        genres = list(CreativePlannerAgent.GENRE_TEMPLATES.keys())
        print(f"Running all {len(genres)} genres...")
    else:
        genres = [g.strip() for g in args.genres.split(",")]
        print(f"Generating {len(genres)} genre(s): {genres}")

    if not genres:
        print("No genres specified. Use --genres, --from-file, or --all")
        return

    # Override config path if specified
    if args.config:
        os.environ["AGNES_CONFIG"] = args.config

    batch_run(
        genres=genres,
        episodes_per_genre=args.episodes,
        style=args.style,
        output_base=args.output,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
