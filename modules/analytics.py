"""Analytics Engine - Data tracking and performance analysis for short dramas."""

import os
import json
import csv
from typing import Optional, Dict, List
from datetime import datetime


class AnalyticsEngine:
    """Track and analyze short drama performance metrics."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "output", "analytics"
        )
        os.makedirs(self.data_dir, exist_ok=True)
        self._data: Dict[str, Dict] = {}
        self._load_data()

    def _load_data(self):
        """Load existing analytics data."""
        data_file = os.path.join(self.data_dir, "analytics.json")
        if os.path.exists(data_file):
            with open(data_file, "r", encoding="utf-8") as f:
                self._data = json.load(f)

    def _save_data(self):
        """Persist analytics data."""
        data_file = os.path.join(self.data_dir, "analytics.json")
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def record_drama(
        self,
        drama_id: str,
        genre: str,
        episodes: int,
        platforms: List[str],
        title: Optional[str] = None,
    ):
        """Register a new drama production."""
        self._data[drama_id] = {
            "id": drama_id,
            "title": title or drama_id,
            "genre": genre,
            "episodes": episodes,
            "platforms": platforms,
            "created_at": datetime.now().isoformat(),
            "metrics": {},
            "episode_metrics": {},
        }
        self._save_data()

    def record_episode_metrics(
        self,
        drama_id: str,
        episode: int,
        metrics: Dict[str, float],
        platform: str = "all",
    ):
        """Record metrics for an episode on a platform.

        Args:
            drama_id: Drama identifier.
            episode: Episode number.
            metrics: Dict of metric_name -> value.
                e.g., {"views": 15000, "likes": 500, "completion_rate": 0.72, "shares": 30}
            platform: Platform name.
        """
        if drama_id not in self._data:
            return

        key = f"ep{episode}:{platform}"
        self._data[drama_id]["episode_metrics"][key] = {
            **metrics,
            "recorded_at": datetime.now().isoformat(),
        }

        # Update overall metrics
        if platform not in self._data[drama_id]["metrics"]:
            self._data[drama_id]["metrics"][platform] = []
        self._data[drama_id]["metrics"][platform].append({
            "episode": episode,
            **metrics,
        })
        self._save_data()

    def get_drama_summary(self, drama_id: str) -> Optional[Dict]:
        """Get summary stats for a drama."""
        drama = self._data.get(drama_id)
        if not drama:
            return None

        summary = {**drama}
        for platform, ep_data in drama.get("metrics", {}).items():
            if ep_data:
                views = [e.get("views", 0) for e in ep_data]
                likes = [e.get("likes", 0) for e in ep_data]
                completion = [e.get("completion_rate", 0) for e in ep_data]
                summary["metrics"][platform] = {
                    "total_views": sum(views),
                    "avg_views": sum(views) / len(views) if views else 0,
                    "total_likes": sum(likes),
                    "avg_completion_rate": sum(completion) / len(completion) if completion else 0,
                    "best_episode": max(range(len(views)), key=lambda i: views[i]) + 1 if views else 0,
                }
        return summary

    def export_csv(self, drama_id: str, csv_path: Optional[str] = None) -> str:
        """Export episode metrics to CSV."""
        if not csv_path:
            csv_path = os.path.join(
                self.data_dir, f"{drama_id}_metrics.csv"
            )

        drama = self._data.get(drama_id)
        if not drama or not drama.get("episode_metrics"):
            return csv_path

        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["episode", "platform", "views", "likes",
                            "completion_rate", "shares", "comments", "recorded_at"])

            for key, data in drama["episode_metrics"].items():
                ep_num, platform = key.split(":")
                writer.writerow([
                    ep_num, platform,
                    data.get("views", 0),
                    data.get("likes", 0),
                    data.get("completion_rate", 0),
                    data.get("shares", 0),
                    data.get("comments", 0),
                    data.get("recorded_at", ""),
                ])

        return csv_path

    def calculate_viral_score(self, metrics: Dict[str, float]) -> float:
        """Calculate a viral potential score (0-100).

        Weighted formula based on engagement patterns.
        """
        score = 0.0
        views = metrics.get("views", 0)
        likes = metrics.get("likes", 0)
        completion = metrics.get("completion_rate", 0)
        shares = metrics.get("shares", 0)

        # Like rate (0-30 points)
        like_rate = likes / max(views, 1)
        score += min(like_rate * 300, 30)

        # Completion rate (0-40 points)
        score += completion * 40

        # Share rate (0-30 points)
        share_rate = shares / max(views, 1)
        score += min(share_rate * 3000, 30)

        return round(min(score, 100), 1)

    def list_dramas(self) -> List[str]:
        """List all recorded drama IDs."""
        return list(self._data.keys())
