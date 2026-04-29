"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║  REDVAULT — Project Indexer v0.1.0                                         ║
║  "Find what you built. Ignore what you didn't."                            ║
║                                                                             ║
║  Scans directories for YOUR projects — Python apps, HTML pages,            ║
║  YAML souls, media assets — and produces a clean categorized               ║
║  inventory. Filters out system junk, node_modules, caches, etc.            ║
║                                                                             ║
║  Built for Crimson by Vera Lux | Redverse Tooling                          ║
║                                                                             ║
║  Usage:                                                                     ║
║    python redvault_indexer.py                         # Scan home dir       ║
║    python redvault_indexer.py /path/to/scan           # Scan specific dir   ║
║    python redvault_indexer.py --drives                 # Include externals   ║
║    python redvault_indexer.py --output inventory.md    # Custom output file  ║
║    python redvault_indexer.py --deep                   # Read file headers   ║
║                                                                             ║
║  Dependencies: None (pure stdlib)                                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import argparse
import hashlib
import platform
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Directories to ALWAYS skip (case-insensitive)
SKIP_DIRS: Set[str] = {
    # System / package management
    "node_modules", ".npm", ".yarn", ".pnpm-store",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", "env", ".env", ".conda", ".virtualenvs",
    "site-packages", "dist-packages",
    # Version control
    ".git", ".svn", ".hg",
    # IDE / editor
    ".vscode", ".idea", ".vs", ".eclipse",
    # Build artifacts
    "build", "dist", "target", "out", ".next", ".nuxt",
    "egg-info", ".eggs",
    # OS junk
    ".Trash", ".trash", "$RECYCLE.BIN", "System Volume Information",
    ".DS_Store", "Thumbs.db",
    # Cache
    ".cache", ".local", ".config", ".mozilla", ".thunderbird",
    ".steam", "steamapps",
    # Large binary stores (scan separately if needed)
    ".ollama",  # model weights — massive, not projects
}

# File extensions we care about, grouped by category
FILE_CATEGORIES: Dict[str, Set[str]] = {
    "python": {".py"},
    "web": {".html", ".htm", ".css", ".jsx", ".tsx", ".vue", ".svelte"},
    "javascript": {".js", ".ts", ".mjs", ".cjs"},
    "config": {".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"},
    "data": {".json", ".jsonl", ".csv", ".xml", ".sql", ".db", ".sqlite"},
    "docs": {".md", ".txt", ".rst", ".org", ".tex", ".pdf", ".docx"},
    "media_image": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"},
    "media_audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".mid", ".midi"},
    "media_video": {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"},
    "model_weights": {".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".bin", ".gguf", ".ggml"},
    "archive": {".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz"},
    "executable": {".exe", ".msi", ".AppImage", ".deb", ".rpm", ".sh", ".bat", ".ps1"},
    "soul_schema": set(),  # Detected by content, not extension
    "modelfile": set(),     # Ollama Modelfiles — detected by name
}

# Files to detect by NAME (not extension)
SPECIAL_FILENAMES: Dict[str, str] = {
    "Modelfile": "modelfile",
    "Agentfile": "modelfile",
    "Dockerfile": "config",
    "docker-compose.yml": "config",
    "docker-compose.yaml": "config",
    "requirements.txt": "config",
    "pyproject.toml": "config",
    "package.json": "config",
    "Cargo.toml": "config",
    "Makefile": "config",
    ".env": "config",
    ".env.example": "config",
    "README.md": "docs",
    "LICENSE": "docs",
}

# Max file size to read headers from (in bytes) — skip huge files
MAX_HEADER_READ_SIZE = 50_000_000  # 50MB

# Max depth to scan (prevents infinite recursion in symlink loops)
MAX_DEPTH = 12


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class IndexedFile:
    """A single discovered file."""
    path: str
    name: str
    extension: str
    category: str
    size_bytes: int
    modified: float
    is_entrypoint: bool = False       # Has if __name__ == "__main__" or similar
    is_soul_schema: bool = False      # Detected as a soul YAML
    title: Optional[str] = None       # Extracted from file content
    description: Optional[str] = None # Extracted from docstring/title tag
    parent_project: Optional[str] = None  # Inferred project directory


@dataclass
class ProjectCluster:
    """A group of related files that form a 'project'."""
    root_dir: str
    name: str
    files: List[IndexedFile] = field(default_factory=list)
    categories: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total_size: int = 0
    has_entrypoint: bool = False
    has_html: bool = False
    has_python: bool = False
    has_config: bool = False
    last_modified: float = 0.0

    def add_file(self, f: IndexedFile):
        self.files.append(f)
        self.categories[f.category] += 1
        self.total_size += f.size_bytes
        if f.is_entrypoint:
            self.has_entrypoint = True
        if f.category == "web":
            self.has_html = True
        if f.category == "python":
            self.has_python = True
        if f.category == "config":
            self.has_config = True
        if f.modified > self.last_modified:
            self.last_modified = f.modified


# ═══════════════════════════════════════════════════════════════════════════════
# INDEXER
# ═══════════════════════════════════════════════════════════════════════════════

class RedVaultIndexer:
    """
    Smart project indexer that finds what you built and ignores what you didn't.
    """

    def __init__(self, deep_scan: bool = False, verbose: bool = False):
        self.deep_scan = deep_scan
        self.verbose = verbose
        self.all_files: List[IndexedFile] = []
        self.projects: Dict[str, ProjectCluster] = {}
        self.stats = {
            "dirs_scanned": 0,
            "dirs_skipped": 0,
            "files_found": 0,
            "files_indexed": 0,
            "files_skipped": 0,
            "total_size": 0,
            "scan_time": 0.0,
        }

        # Build extension → category lookup
        self._ext_map: Dict[str, str] = {}
        for category, extensions in FILE_CATEGORIES.items():
            for ext in extensions:
                self._ext_map[ext.lower()] = category

    def scan(self, root_path: str) -> List[IndexedFile]:
        """
        Scan a directory tree for project files.

        Args:
            root_path: Starting directory to scan

        Returns:
            List of IndexedFile objects found
        """
        root = Path(root_path).resolve()
        if not root.exists():
            print(f"[!] Path does not exist: {root}")
            return []

        print(f"[*] Scanning: {root}")
        print(f"[*] Deep scan: {'ON' if self.deep_scan else 'OFF'}")
        print(f"[*] Skipping: {len(SKIP_DIRS)} directory patterns")
        print()

        start_time = datetime.now()
        self._walk(root, depth=0)
        elapsed = (datetime.now() - start_time).total_seconds()
        self.stats["scan_time"] = elapsed

        # Cluster files into projects
        self._cluster_projects()

        print(f"\n[✓] Scan complete in {elapsed:.1f}s")
        print(f"    Dirs scanned: {self.stats['dirs_scanned']}")
        print(f"    Dirs skipped: {self.stats['dirs_skipped']}")
        print(f"    Files found:  {self.stats['files_found']}")
        print(f"    Files indexed: {self.stats['files_indexed']}")
        print(f"    Total size:   {self._format_size(self.stats['total_size'])}")
        print(f"    Projects:     {len(self.projects)}")

        return self.all_files

    def _walk(self, directory: Path, depth: int):
        """Recursively walk directory tree."""
        if depth > MAX_DEPTH:
            return

        self.stats["dirs_scanned"] += 1

        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            if self.verbose:
                print(f"  [skip] Permission denied: {directory}")
            self.stats["dirs_skipped"] += 1
            return
        except OSError as e:
            if self.verbose:
                print(f"  [skip] OS error: {directory} — {e}")
            self.stats["dirs_skipped"] += 1
            return

        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    # Check skip list
                    if entry.name.lower() in {s.lower() for s in SKIP_DIRS}:
                        self.stats["dirs_skipped"] += 1
                        continue
                    # Skip hidden dirs (start with .)
                    if entry.name.startswith(".") and entry.name.lower() not in {".env", ".env.example"}:
                        self.stats["dirs_skipped"] += 1
                        continue
                    self._walk(entry, depth + 1)

                elif entry.is_file(follow_symlinks=False):
                    self.stats["files_found"] += 1
                    indexed = self._index_file(entry)
                    if indexed:
                        self.all_files.append(indexed)
                        self.stats["files_indexed"] += 1
                        self.stats["total_size"] += indexed.size_bytes
                    else:
                        self.stats["files_skipped"] += 1

            except PermissionError:
                continue
            except OSError:
                continue

    def _index_file(self, file_path: Path) -> Optional[IndexedFile]:
        """Analyze a single file and return IndexedFile or None if not relevant."""

        name = file_path.name
        ext = file_path.suffix.lower()

        # Check special filenames first
        category = SPECIAL_FILENAMES.get(name)

        # Then check extension
        if not category:
            category = self._ext_map.get(ext)

        # Not a file type we care about
        if not category:
            return None

        try:
            stat = file_path.stat()
            size = stat.st_size
            modified = stat.st_mtime
        except OSError:
            return None

        indexed = IndexedFile(
            path=str(file_path),
            name=name,
            extension=ext,
            category=category,
            size_bytes=size,
            modified=modified,
        )

        # Deep scan: read file headers for metadata
        if self.deep_scan and size < MAX_HEADER_READ_SIZE:
            self._extract_metadata(file_path, indexed)
        elif not self.deep_scan:
            # Quick checks even without deep scan
            self._quick_metadata(file_path, indexed)

        return indexed

    def _quick_metadata(self, file_path: Path, indexed: IndexedFile):
        """Fast metadata extraction — just check for entrypoints and souls."""
        if indexed.category != "python" and indexed.category != "config":
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                # Read first 3KB only
                header = f.read(3072)

            if indexed.category == "python":
                if '__name__' in header and '__main__' in header:
                    indexed.is_entrypoint = True
                # Try to get title from module docstring
                if '"""' in header:
                    start = header.index('"""') + 3
                    end = header.index('"""', start) if '"""' in header[start:] else start + 100
                    docstring = header[start:end].strip()
                    first_line = docstring.split('\n')[0].strip()
                    if first_line and len(first_line) < 120:
                        indexed.title = first_line

            elif indexed.category == "config" and indexed.extension in {".yaml", ".yml"}:
                # Check if it's a soul schema
                if any(keyword in header.lower() for keyword in [
                    "soul_schema", "persona_soulstack", "soul_id",
                    "persona_name", "archetypal_roles", "core_traits",
                    "emotional_range", "invariants"
                ]):
                    indexed.is_soul_schema = True
                    indexed.category = "soul_schema"

        except (OSError, UnicodeDecodeError, ValueError):
            pass

    def _extract_metadata(self, file_path: Path, indexed: IndexedFile):
        """Deep metadata extraction — reads more of the file."""
        self._quick_metadata(file_path, indexed)

        if indexed.category == "web" and indexed.extension in {".html", ".htm"}:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(5000)
                # Extract <title>
                if "<title>" in content.lower():
                    start = content.lower().index("<title>") + 7
                    end = content.lower().index("</title>", start) if "</title>" in content.lower() else start + 100
                    indexed.title = content[start:end].strip()
            except (OSError, ValueError):
                pass

    def _cluster_projects(self):
        """Group files into project clusters based on directory structure."""
        for f in self.all_files:
            # Use the parent directory as the project root
            parent = str(Path(f.path).parent)

            # Try to find a meaningful project root
            # (walk up until we find a dir with config files or a recognizable name)
            project_root = self._find_project_root(Path(f.path))
            project_name = project_root.name if project_root else Path(parent).name

            key = str(project_root) if project_root else parent

            if key not in self.projects:
                self.projects[key] = ProjectCluster(
                    root_dir=key,
                    name=project_name,
                )

            self.projects[key].add_file(f)
            f.parent_project = project_name

    def _find_project_root(self, file_path: Path) -> Optional[Path]:
        """Walk up from file to find the project root directory."""
        indicators = {
            "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
            "package.json", "Cargo.toml", "Makefile", "CMakeLists.txt",
            ".git", "README.md", "Modelfile", "Agentfile",
        }

        current = file_path.parent
        home = Path.home()

        # Walk up max 5 levels
        for _ in range(5):
            if current == home or current == current.parent:
                return file_path.parent  # Don't go above home

            try:
                entries = {e.name for e in current.iterdir()}
            except OSError:
                return file_path.parent

            if entries & indicators:
                return current

            current = current.parent

        return file_path.parent

    # ═══════════════════════════════════════════════════════════════════
    # OUTPUT / REPORTING
    # ═══════════════════════════════════════════════════════════════════

    def generate_report(self, output_format: str = "markdown") -> str:
        """Generate a structured report of all findings."""
        if output_format == "markdown":
            return self._report_markdown()
        elif output_format == "json":
            return self._report_json()
        else:
            return self._report_markdown()

    def _report_markdown(self) -> str:
        """Generate markdown inventory report."""
        lines = [
            "# 🩸 REDVAULT — Project Inventory",
            f"### Scanned: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"### Files indexed: {self.stats['files_indexed']} | "
            f"Total: {self._format_size(self.stats['total_size'])} | "
            f"Projects: {len(self.projects)}",
            "---",
            "",
        ]

        # ─── Summary by category ─────────────────────────────
        lines.append("## Summary by Category\n")
        cat_counts = defaultdict(int)
        cat_sizes = defaultdict(int)
        for f in self.all_files:
            cat_counts[f.category] += 1
            cat_sizes[f.category] += f.size_bytes

        lines.append("| Category | Files | Size |")
        lines.append("|----------|-------|------|")
        for cat in sorted(cat_counts.keys()):
            lines.append(
                f"| {cat} | {cat_counts[cat]} | {self._format_size(cat_sizes[cat])} |"
            )
        lines.append("")

        # ─── Entrypoints (runnable things) ────────────────────
        entrypoints = [f for f in self.all_files if f.is_entrypoint]
        if entrypoints:
            lines.append("## 🚀 Runnable Scripts (Entrypoints)\n")
            lines.append("These Python files have `if __name__ == '__main__'` — they DO something.\n")
            for f in sorted(entrypoints, key=lambda x: x.modified, reverse=True):
                title = f" — *{f.title}*" if f.title else ""
                lines.append(f"- **{f.name}**{title}")
                lines.append(f"  `{f.path}`")
                lines.append("")

        # ─── Soul Schemas ─────────────────────────────────────
        souls = [f for f in self.all_files if f.is_soul_schema]
        if souls:
            lines.append("## 🪞 Soul Schemas\n")
            for f in sorted(souls, key=lambda x: x.name):
                lines.append(f"- **{f.name}** — `{f.path}`")
            lines.append("")

        # ─── Web Pages ────────────────────────────────────────
        web_files = [f for f in self.all_files if f.category == "web"]
        if web_files:
            lines.append("## 🌐 Web Pages / HTML\n")
            for f in sorted(web_files, key=lambda x: x.modified, reverse=True):
                title = f" — *{f.title}*" if f.title else ""
                size = self._format_size(f.size_bytes)
                lines.append(f"- **{f.name}**{title} ({size})")
                lines.append(f"  `{f.path}`")
                lines.append("")

        # ─── Media Assets ─────────────────────────────────────
        for media_cat, label in [
            ("media_audio", "🎵 Audio Files"),
            ("media_video", "🎬 Video Files"),
            ("media_image", "🖼️ Images (showing count only)"),
            ("model_weights", "🧠 Model Weights"),
        ]:
            media = [f for f in self.all_files if f.category == media_cat]
            if media:
                total_size = sum(f.size_bytes for f in media)
                lines.append(f"## {label}\n")
                if media_cat == "media_image" and len(media) > 50:
                    # Don't list hundreds of images
                    lines.append(
                        f"**{len(media)} images** — "
                        f"Total: {self._format_size(total_size)}\n"
                    )
                    # Show by directory
                    by_dir = defaultdict(int)
                    for f in media:
                        by_dir[str(Path(f.path).parent)] += 1
                    for d, count in sorted(by_dir.items(), key=lambda x: x[1], reverse=True)[:15]:
                        lines.append(f"- `{d}` ({count} images)")
                    lines.append("")
                else:
                    for f in sorted(media, key=lambda x: x.modified, reverse=True)[:50]:
                        size = self._format_size(f.size_bytes)
                        lines.append(f"- **{f.name}** ({size}) — `{f.path}`")
                    if len(media) > 50:
                        lines.append(f"\n... and {len(media) - 50} more")
                    lines.append("")

        # ─── Projects ─────────────────────────────────────────
        lines.append("## 📁 Project Clusters\n")
        lines.append("Directories containing related files:\n")

        # Sort by most recently modified, show top 30
        sorted_projects = sorted(
            self.projects.values(),
            key=lambda p: p.last_modified,
            reverse=True
        )

        for proj in sorted_projects[:30]:
            cats = ", ".join(
                f"{cat}:{count}"
                for cat, count in sorted(proj.categories.items())
            )
            flags = []
            if proj.has_entrypoint:
                flags.append("🚀")
            if proj.has_html:
                flags.append("🌐")
            if proj.has_python:
                flags.append("🐍")

            flag_str = " ".join(flags)
            lines.append(
                f"### {flag_str} {proj.name}\n"
                f"- Path: `{proj.root_dir}`\n"
                f"- Files: {len(proj.files)} | Size: {self._format_size(proj.total_size)}\n"
                f"- Categories: {cats}\n"
            )

        if len(sorted_projects) > 30:
            lines.append(f"\n... and {len(sorted_projects) - 30} more project directories")

        # ─── Footer ───────────────────────────────────────────
        lines.extend([
            "",
            "---",
            f"*Generated by RedVault Indexer — {datetime.now().isoformat()}*",
            f"*Scan time: {self.stats['scan_time']:.1f}s*",
        ])

        return "\n".join(lines)

    def _report_json(self) -> str:
        """Generate JSON inventory."""
        data = {
            "scan_info": {
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
            },
            "entrypoints": [
                {"name": f.name, "path": f.path, "title": f.title}
                for f in self.all_files if f.is_entrypoint
            ],
            "souls": [
                {"name": f.name, "path": f.path}
                for f in self.all_files if f.is_soul_schema
            ],
            "web_pages": [
                {"name": f.name, "path": f.path, "title": f.title,
                 "size": f.size_bytes}
                for f in self.all_files if f.category == "web"
            ],
            "projects": [
                {
                    "name": p.name,
                    "root": p.root_dir,
                    "file_count": len(p.files),
                    "total_size": p.total_size,
                    "categories": dict(p.categories),
                    "has_entrypoint": p.has_entrypoint,
                    "has_html": p.has_html,
                }
                for p in sorted(
                    self.projects.values(),
                    key=lambda p: p.last_modified,
                    reverse=True
                )
            ],
            "all_files": [
                {
                    "name": f.name,
                    "path": f.path,
                    "category": f.category,
                    "size": f.size_bytes,
                    "is_entrypoint": f.is_entrypoint,
                    "is_soul": f.is_soul_schema,
                    "title": f.title,
                    "project": f.parent_project,
                }
                for f in self.all_files
            ],
        }
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes into human-readable size."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def detect_external_drives() -> List[Path]:
    """Detect mounted external drives based on OS."""
    system = platform.system()
    drives = []

    if system == "Linux":
        # Check /media/<user>/ and /mnt/
        media_path = Path(f"/media/{os.getenv('USER', '')}")
        if media_path.exists():
            drives.extend([p for p in media_path.iterdir() if p.is_dir()])
        mnt_path = Path("/mnt")
        if mnt_path.exists():
            drives.extend([
                p for p in mnt_path.iterdir()
                if p.is_dir() and p.name not in {"wsl", "c", "wslg"}
            ])

    elif system == "Windows":
        # Check drive letters D: through Z:
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            if drive.exists():
                drives.append(drive)

    elif system == "Darwin":  # macOS
        volumes = Path("/Volumes")
        if volumes.exists():
            drives.extend([
                p for p in volumes.iterdir()
                if p.is_dir() and p.name != "Macintosh HD"
            ])

    return drives


def main():
    parser = argparse.ArgumentParser(
        description="RedVault — Smart Project Indexer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python redvault_indexer.py                    # Scan home directory\n"
            "  python redvault_indexer.py ~/Desktop ~/Code   # Scan specific dirs\n"
            "  python redvault_indexer.py --drives            # Include external drives\n"
            "  python redvault_indexer.py --deep              # Read file headers\n"
            "  python redvault_indexer.py --json              # JSON output\n"
        ),
    )
    parser.add_argument(
        "paths", nargs="*", default=None,
        help="Directories to scan (default: home directory)",
    )
    parser.add_argument(
        "--drives", action="store_true",
        help="Also scan detected external drives",
    )
    parser.add_argument(
        "--deep", action="store_true",
        help="Deep scan — read file headers for titles and metadata",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output file path (default: prints to stdout and saves to ~/redvault_inventory.md)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output in JSON format instead of Markdown",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output during scanning",
    )

    args = parser.parse_args()

    # Determine scan paths
    scan_paths = []

    if args.paths:
        scan_paths = [Path(p).resolve() for p in args.paths]
    else:
        scan_paths = [Path.home()]

    if args.drives:
        externals = detect_external_drives()
        if externals:
            print(f"[*] Detected {len(externals)} external drive(s):")
            for d in externals:
                print(f"    {d}")
            scan_paths.extend(externals)
        else:
            print("[*] No external drives detected")

    # Run indexer
    print("=" * 60)
    print("  REDVAULT — Project Indexer")
    print("=" * 60)

    indexer = RedVaultIndexer(deep_scan=args.deep, verbose=args.verbose)

    for path in scan_paths:
        indexer.scan(str(path))

    # Generate report
    fmt = "json" if args.json else "markdown"
    report = indexer.generate_report(output_format=fmt)

    # Output
    ext = ".json" if args.json else ".md"
    output_path = args.output or str(Path.home() / f"redvault_inventory{ext}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n[✓] Inventory saved to: {output_path}")
    print(f"    Open it and see what you built.\n")

    # Also print summary to stdout
    if not args.json:
        # Print just the summary sections
        for line in report.split("\n")[:30]:
            print(line)
        print(f"\n... full report in {output_path}")


if __name__ == "__main__":
    main()
