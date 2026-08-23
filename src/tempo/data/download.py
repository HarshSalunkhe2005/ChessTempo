"""Download a Lichess monthly game archive and filter it down to a rating
band, so you don't need to pull (and store) the full multi-GB dump just to
get a training set.

Usage:
    python -m tempo.data.download --month 2024-01 --min-rating 1200 --max-rating 1800
"""
from __future__ import annotations

import argparse
import io
import re
from pathlib import Path

import requests
import zstandard as zstd
from tqdm import tqdm

LICHESS_BASE = "https://database.lichess.org/standard"
DATA_DIR = Path(__file__).resolve().parents[3] / "data"

_RATING_RE = re.compile(r'\[(WhiteElo|BlackElo) "(\d+)"\]')


def download_archive(month: str, dest_dir: Path = DATA_DIR) -> Path:
    """Stream-download the raw .pgn.zst archive for a given YYYY-MM month."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    url = f"{LICHESS_BASE}/lichess_db_standard_rated_{month}.pgn.zst"
    dest = dest_dir / f"lichess_{month}.pgn.zst"

    if dest.exists():
        print(f"Already downloaded: {dest}")
        return dest

    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=month) as bar:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            f.write(chunk)
            bar.update(len(chunk))

    return dest


def filter_by_rating(
    archive_path: Path,
    min_rating: int,
    max_rating: int,
    max_games: int | None = None,
) -> Path:
    """Stream-decompress the .zst archive and write out only games where
    both players fall in [min_rating, max_rating], as plain PGN text.

    Avoids ever holding the full decompressed archive (tens of GB) on disk
    or in memory at once.
    """
    out_path = archive_path.with_name(
        archive_path.stem.replace(".pgn", "") + f"_r{min_rating}-{max_rating}.pgn"
    )
    if out_path.exists():
        print(f"Already filtered: {out_path}")
        return out_path

    dctx = zstd.ZstdDecompressor()
    kept = 0

    with open(archive_path, "rb") as fh, dctx.stream_reader(fh) as reader:
        text_stream = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
        with open(out_path, "w", encoding="utf-8") as out:
            game_lines: list[str] = []
            ratings: dict[str, int] = {}

            for line in text_stream:
                game_lines.append(line)
                m = _RATING_RE.match(line.strip())
                if m:
                    ratings[m.group(1)] = int(m.group(2))

                # A blank line after the movetext ends a game record.
                if line.strip() == "" and game_lines and game_lines[-2].startswith("1."):
                    white, black = ratings.get("WhiteElo"), ratings.get("BlackElo")
                    if white and black and min_rating <= white <= max_rating and min_rating <= black <= max_rating:
                        out.writelines(game_lines)
                        kept += 1
                        if max_games and kept >= max_games:
                            break
                    game_lines, ratings = [], {}

    print(f"Kept {kept} games in rating band [{min_rating}, {max_rating}] -> {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True, help="YYYY-MM, e.g. 2024-01")
    parser.add_argument("--min-rating", type=int, default=1200)
    parser.add_argument("--max-rating", type=int, default=1800)
    parser.add_argument("--max-games", type=int, default=None, help="Cap games kept, for a quick first run")
    args = parser.parse_args()

    archive = download_archive(args.month)
    filter_by_rating(archive, args.min_rating, args.max_rating, args.max_games)


if __name__ == "__main__":
    main()
