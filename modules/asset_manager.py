"""素材管理模块 - 短剧产出资产的索引与管理

功能：
1. 自动扫描 output 目录，建立素材索引
2. 按题材/集数/角色分类查找
3. 生成素材统计报告
4. 支持快速浏览所有产出
"""

import os
import json
import glob
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class AssetEntry:
    """单个素材条目"""
    id: str                              # 唯一标识: genre_ep001_script
    genre: str                           # 题材
    episode: int                         # 集数
    asset_type: str                      # 类型: script/storyboard/images/audio/video/outline
    file_path: str                       # 文件路径
    file_size: int = 0                   # 文件大小（字节）
    created_at: str = ""                 # 创建时间
    metadata: Dict = field(default_factory=dict)


@dataclass
class AssetReport:
    """素材统计报告"""
    total_assets: int = 0
    total_size_mb: float = 0.0
    genres: Dict[str, int] = field(default_factory=dict)    # 题材 → 数量
    episodes_by_genre: Dict[str, int] = field(default_factory=dict)  # 题材 → 集数
    asset_types: Dict[str, int] = field(default_factory=dict)  # 类型 → 数量
    latest_update: str = ""
    entries: List[AssetEntry] = field(default_factory=list)


class AssetManager:
    """短剧素材管理器"""

    def __init__(self, output_base: str = "output"):
        self.output_base = output_base
        self._cache: Optional[AssetReport] = None

    def _scan_files(self) -> List[AssetEntry]:
        """扫描 output 目录下所有产出文件"""
        entries = []
        
        if not os.path.exists(self.output_base):
            return entries

        for root, dirs, files in os.walk(self.output_base):
            # 跳过临时文件和中间缓存
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "web_tts")]
            
            for filename in files:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, self.output_base)
                
                # 跳过 analytics 目录和 .git 目录
                if ".git" in rel_path or rel_path.startswith("analytics"):
                    continue

                # 推断题材和集数
                parts = rel_path.split(os.sep)
                genre = parts[0] if len(parts) > 1 else "default"
                episode = 0
                
                # 从路径中解析集数 (ep001, ep002, ...)
                for i, part in enumerate(parts):
                    if part.startswith("ep") and len(part) >= 4:
                        try:
                            episode = int(part[2:])
                        except ValueError:
                            pass
                        break

                # 推断资产类型
                asset_type = self._classify_asset(filename)
                
                # 生成唯一ID
                asset_id = f"{genre}_ep{episode:03d}_{asset_type}"
                if episode > 0 and asset_type:
                    asset_id = f"{genre}_{asset_id}"

                # 获取文件大小
                try:
                    file_size = os.path.getsize(filepath)
                except OSError:
                    file_size = 0

                # 获取创建时间
                try:
                    mtime = os.path.getmtime(filepath)
                    created_at = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                except OSError:
                    created_at = ""

                entry = AssetEntry(
                    id=asset_id,
                    genre=genre,
                    episode=episode,
                    asset_type=asset_type,
                    file_path=filepath,
                    file_size=file_size,
                    created_at=created_at,
                )
                entries.append(entry)

        return entries

    def _classify_asset(self, filename: str) -> str:
        """根据文件名分类资产类型"""
        name_lower = filename.lower()
        
        if name_lower == "script.md" or name_lower.startswith("script_"):
            return "script"
        elif name_lower == "storyboard.json" or name_lower.startswith("storyboard_"):
            return "storyboard"
        elif name_lower == "outline.json" or name_lower.startswith("outline_"):
            return "outline"
        elif name_lower == "result.json" or name_lower.startswith("result_"):
            return "result"
        elif name_lower == "planning.json":
            return "planning"
        elif name_lower == "overall_result.json":
            return "report"
        elif name_lower.endswith(".mp3") or name_lower.endswith(".wav") or name_lower.endswith(".m4a"):
            return "audio"
        elif name_lower.endswith(".mp4") or name_lower.endswith(".avi") or name_lower.endswith(".mov"):
            return "video"
        elif name_lower.endswith(".json"):
            return "metadata"
        elif any(ext in name_lower for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
            return "image"
        elif name_lower.endswith(".srt"):
            return "subtitle"
        else:
            return "other"

    def refresh(self) -> AssetReport:
        """刷新素材索引"""
        entries = self._scan_files()
        
        # 统计
        genres = {}
        episodes_by_genre = {}
        asset_types = {}
        total_size = 0
        latest = ""
        
        for e in entries:
            genres[e.genre] = genres.get(e.genre, 0) + 1
            if e.episode > 0:
                episodes_by_genre[e.genre] = max(
                    episodes_by_genre.get(e.genre, 0), e.episode
                )
            asset_types[e.asset_type] = asset_types.get(e.asset_type, 0) + 1
            total_size += e.file_size
            
            if e.created_at and e.created_at > latest:
                latest = e.created_at

        report = AssetReport(
            total_assets=len(entries),
            total_size_mb=round(total_size / (1024 * 1024), 2),
            genres=genres,
            episodes_by_genre=episodes_by_genre,
            asset_types=asset_types,
            latest_update=latest,
            entries=entries,
        )
        
        self._cache = report
        return report

    def get_report(self) -> AssetReport:
        """获取素材统计报告"""
        if self._cache is None:
            return self.refresh()
        return self._cache

    def list_by_genre(self, genre: str) -> List[AssetEntry]:
        """按题材列出素材"""
        report = self.get_report()
        return [e for e in report.entries if e.genre == genre]

    def list_by_episode(self, genre: str, episode: int) -> List[AssetEntry]:
        """按题材和集数列出素材"""
        report = self.get_report()
        return [
            e for e in report.entries
            if e.genre == genre and e.episode == episode
        ]

    def list_by_type(self, asset_type: str) -> List[AssetEntry]:
        """按资产类型列出素材"""
        report = self.get_report()
        return [e for e in report.entries if e.asset_type == asset_type]

    def get_all_genres(self) -> List[str]:
        """获取所有题材列表"""
        report = self.get_report()
        return sorted(report.genres.keys())

    def print_report(self):
        """打印格式化的素材报告"""
        report = self.get_report()

        print("\n" + "=" * 60)
        print("  📚 短剧素材管理报告")
        print("=" * 60)
        print(f"\n  总素材数: {report.total_assets} 个")
        print(f"  总大小:   {report.total_size_mb} MB")
        print(f"  最新更新: {report.latest_update or '无'}")

        print(f"\n  📂 题材分布 ({len(report.genres)} 个题材):")
        for genre, count in sorted(report.genres.items()):
            eps = report.episodes_by_genre.get(genre, "?")
            print(f"    {genre}: {count} 个文件 ({eps} 集)")

        print(f"\n  📁 资产类型:")
        for atype, count in sorted(report.asset_types.items()):
            print(f"    {atype}: {count} 个")

        print()

    def print_genre_detail(self, genre: str):
        """打印指定题材的详细列表"""
        entries = self.list_by_genre(genre)
        
        print(f"\n{'=' * 60}")
        print(f"  📂 {genre} — 详细素材列表 ({len(entries)} 个)")
        print("=" * 60)

        # 按集数分组
        by_episode = {}
        for e in entries:
            ep_key = f"第{e.episode:03d}集" if e.episode > 0 else "总体"
            by_episode.setdefault(ep_key, []).append(e)

        for ep_key in sorted(by_episode.keys()):
            items = by_episode[ep_key]
            print(f"\n  {ep_key}:")
            for item in items:
                size_kb = item.file_size / 1024
                size_str = f"({size_kb:.1f}KB)" if size_kb > 0 else ""
                print(f"    [{item.asset_type:10s}] {os.path.basename(item.file_path)} {size_str}")

        print()

    def export_json(self, output_path: str):
        """导出素材索引为 JSON 文件"""
        report = self.get_report()
        data = {
            "total_assets": report.total_assets,
            "total_size_mb": report.total_size_mb,
            "genres": report.genres,
            "episodes_by_genre": report.episodes_by_genre,
            "asset_types": report.asset_types,
            "latest_update": report.latest_update,
            "entries": [asdict(e) for e in report.entries],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  素材索引已导出: {output_path}")


# ===== 便捷函数 =====

def quick_asset_report(output_base: str = "output"):
    """快速查看素材报告"""
    manager = AssetManager(output_base=output_base)
    manager.print_report()
    return manager


if __name__ == "__main__":
    print("=" * 50)
    print("  素材管理模块测试")
    print("=" * 50)
    
    manager = quick_asset_report()
    
    # 列出所有题材
    genres = manager.get_all_genres()
    print(f"\n题材列表: {genres}")
    
    # 导出JSON
    manager.export_json("output/asset_index.json")
