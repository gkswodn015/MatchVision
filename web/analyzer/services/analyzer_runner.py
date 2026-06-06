import os
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings


@dataclass(frozen=True)
class AnalyzerRunResult:
    detected_video_name: str
    topview_video_name: str
    team_ids: dict = field(default_factory=dict)


class AnalyzerRunError(RuntimeError):
    pass


def run_analyzer_for_match(match, log_callback=None) -> AnalyzerRunResult:
    """
    Run Analyzer/main.py as-is.

    This preserves the desktop Analyzer workflow: keyframe selection,
    landmark picking, role sample picking, OpenCV progress windows, and the
    existing VideoPipeline behavior. The web app only launches it, records
    logs, and imports the resulting videos.
    """
    project_root = Path(settings.BASE_DIR).parent
    analyzer_dir = project_root / "Analyzer"
    analyzer_main = analyzer_dir / "main.py"
    python_exe = project_root / "venv" / "Scripts" / "python.exe"
    video_path = Path(match.video.path)

    if not video_path.exists():
        raise AnalyzerRunError(f"Uploaded video not found: {video_path}")
    if not analyzer_main.exists():
        raise AnalyzerRunError(f"Analyzer entrypoint not found: {analyzer_main}")
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    video_stem = video_path.stem
    analyzer_result_dir = analyzer_dir / "result"
    detected_src = analyzer_result_dir / f"{video_stem}_detected.mp4"
    topview_src = analyzer_result_dir / f"{video_stem}_topview.mp4"
    team_ids_src = analyzer_result_dir / f"{video_stem}_team_ids.json"

    _remove_stale_output(detected_src)
    _remove_stale_output(topview_src)
    _remove_stale_output(team_ids_src)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(analyzer_dir)
    env["PYTHONUNBUFFERED"] = "1"

    _log(log_callback, f"Starting Analyzer: {video_path}")
    process = subprocess.Popen(
        [str(python_exe), str(analyzer_main), str(video_path)],
        cwd=str(analyzer_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert process.stdout is not None
    for line in process.stdout:
        _log(log_callback, line.rstrip())

    return_code = process.wait()
    if return_code != 0:
        raise AnalyzerRunError(f"Analyzer failed with exit code {return_code}.")

    result = import_analyzer_result_videos(match)
    _log(log_callback, "Analyzer completed successfully.")
    return result


def import_analyzer_result_videos(match) -> AnalyzerRunResult:
    project_root = Path(settings.BASE_DIR).parent
    analyzer_result_dir = project_root / "Analyzer" / "result"
    video_stem = Path(match.video.path).stem

    detected_src = analyzer_result_dir / f"{video_stem}_detected.mp4"
    topview_src = analyzer_result_dir / f"{video_stem}_topview.mp4"
    team_ids_src = analyzer_result_dir / f"{video_stem}_team_ids.json"

    if not detected_src.exists() or not topview_src.exists():
        detected_src, topview_src = _find_latest_result_pair(analyzer_result_dir, video_stem)
        if detected_src is not None:
            team_ids_src = detected_src.with_name(
                detected_src.name.replace("_detected.mp4", "_team_ids.json")
            )

    if detected_src is None or topview_src is None:
        raise AnalyzerRunError(
            f"Analyzer result videos not found for video stem: {video_stem}"
        )

    media_result_dir = Path(settings.MEDIA_ROOT) / "analysis_results"
    media_result_dir.mkdir(parents=True, exist_ok=True)

    detected_name = f"analysis_results/match_{match.id}_{_web_mp4_name(detected_src)}"
    topview_name = f"analysis_results/match_{match.id}_{_web_mp4_name(topview_src)}"

    detected_dst = Path(settings.MEDIA_ROOT) / detected_name
    topview_dst = Path(settings.MEDIA_ROOT) / topview_name

    _make_browser_playable_mp4(detected_src, detected_dst)
    _make_browser_playable_mp4(topview_src, topview_dst)

    return AnalyzerRunResult(
        detected_video_name=detected_name,
        topview_video_name=topview_name,
        team_ids=_load_team_ids(team_ids_src),
    )


def _remove_stale_output(path: Path) -> None:
    if path.exists():
        path.unlink()


def _load_team_ids(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def _web_mp4_name(source: Path) -> str:
    return f"{source.stem}_web.mp4"


def _make_browser_playable_mp4(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = _ffmpeg_executable()
    if ffmpeg is None:
        shutil.copy2(source, destination)
        return

    temp_destination = destination.with_suffix(".tmp.mp4")
    if temp_destination.exists():
        temp_destination.unlink()

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(temp_destination),
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0 or not temp_destination.exists():
        shutil.copy2(source, destination)
        return

    if destination.exists():
        destination.unlink()
    temp_destination.replace(destination)


def _ffmpeg_executable() -> str | None:
    try:
        import imageio_ffmpeg
    except ImportError:
        return shutil.which("ffmpeg")

    return imageio_ffmpeg.get_ffmpeg_exe()


def _log(log_callback, message: str) -> None:
    if message:
        print(message)
    if log_callback is not None:
        log_callback(message)


def _find_latest_result_pair(
    result_dir: Path,
    video_stem: str,
) -> tuple[Path | None, Path | None]:
    if not result_dir.exists():
        return None, None

    detected_candidates = sorted(
        result_dir.glob(f"{video_stem}*_detected.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for detected in detected_candidates:
        topview_name = detected.name.replace("_detected.mp4", "_topview.mp4")
        topview = result_dir / topview_name
        if topview.exists():
            return detected, topview

    detected_candidates = sorted(
        result_dir.glob("*_detected.mp4"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for detected in detected_candidates:
        topview_name = detected.name.replace("_detected.mp4", "_topview.mp4")
        topview = result_dir / topview_name
        if topview.exists():
            return detected, topview

    return None, None
