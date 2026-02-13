"""FFmpeg-based layer comp compositing for Moho Render Farm."""
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Callable


def get_ffmpeg_path():
    """Get the path to the bundled ffmpeg executable."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "ffmpeg", "ffmpeg.exe")


def compose_layer_comps(output_dir: str, framerate: int = 24,
                        ffmpeg_path: str = None,
                        on_output: Optional[Callable[[str], None]] = None,
                        reverse_order: bool = False) -> Optional[str]:
    """Compose all layer comp PNG sequences into a single MP4.

    Default order (alphabetical):
    - LAST alphabetically = background (bottom layer)
    - FIRST alphabetically = foreground (top layer)

    Reverse order:
    - FIRST alphabetically = background (bottom layer)
    - LAST alphabetically = foreground (top layer)

    Uses ffmpeg overlay filter to composite all layers.

    Args:
        output_dir: Directory containing layer comp subfolders with PNG sequences
        framerate: Frame rate for the output video
        ffmpeg_path: Path to ffmpeg executable (uses bundled if None)
        on_output: Callback for log messages
        reverse_order: If True, reverse the compositing order (first alpha = background)

    Returns:
        Path to the composed MP4 file, or None if failed
    """
    if ffmpeg_path is None:
        ffmpeg_path = get_ffmpeg_path()

    if not os.path.exists(ffmpeg_path):
        if on_output:
            on_output(f"[ffmpeg] ERROR: ffmpeg not found at {ffmpeg_path}")
        return None

    output_path = Path(output_dir)
    if not output_path.is_dir():
        if on_output:
            on_output(f"[ffmpeg] ERROR: Output directory not found: {output_dir}")
        return None

    # Find layer comp subfolders containing PNG sequences
    layer_folders = []
    for item in sorted(output_path.iterdir()):
        if item.is_dir():
            pngs = sorted(item.glob("*.png"))
            if pngs:
                layer_folders.append((item.name, item, pngs))

    if len(layer_folders) < 2:
        if on_output:
            on_output(f"[ffmpeg] Need at least 2 layer comp folders to compose, found {len(layer_folders)}")
        return None

    # Determine the PNG filename pattern for each folder
    # Moho uses: name_00001.png or name00001.png (frame numbers can start at any value)
    def _detect_pattern(pngs):
        """Detect the ffmpeg-compatible sequence pattern, start number, and frame count."""
        first = pngs[0].name
        # Find the last sequence of digits before .png (the frame number)
        match = re.search(r'(\d+)\.png$', first)
        if match:
            digits = match.group(1)
            num_digits = len(digits)
            start_number = int(digits)
            prefix = first[:match.start(1)]
            return f"{prefix}%0{num_digits}d.png", start_number, len(pngs)
        return None, 0, 0

    if on_output:
        on_output(f"[ffmpeg] Found {len(layer_folders)} layer comp folders to compose:")
        for name, folder, pngs in layer_folders:
            pattern, start_num, count = _detect_pattern(pngs)
            first_file = pngs[0].name if pngs else "?"
            on_output(f"[ffmpeg]   {name}: {count} frames, start={start_num}, pattern={pattern}, first={first_file}")

    # Default: last alphabetically = background, first = foreground
    # Reverse: first alphabetically = background, last = foreground
    if reverse_order:
        layers_bg_to_fg = list(layer_folders)  # A (bg) first, Z (fg) last
    else:
        layers_bg_to_fg = list(reversed(layer_folders))  # Z (bg) first, A (fg) last

    # Build ffmpeg command
    cmd = [ffmpeg_path, "-y"]  # -y to overwrite

    # Determine the shortest frame count across all valid layers
    valid_layers = []
    for name, folder, pngs in layers_bg_to_fg:
        pattern, start_num, count = _detect_pattern(pngs)
        if pattern is None:
            if on_output:
                on_output(f"[ffmpeg] WARNING: Could not detect frame pattern in {name}, skipping")
            continue
        valid_layers.append((name, folder, pattern, start_num, count))

    if len(valid_layers) < 2:
        if on_output:
            on_output("[ffmpeg] ERROR: Not enough valid layer inputs")
        return None

    # Use shortest frame count so all inputs match
    min_frames = min(count for _, _, _, _, count in valid_layers)

    # Add input for each layer
    for name, folder, pattern, start_num, count in valid_layers:
        input_path = str(folder / pattern)
        cmd.extend([
            "-framerate", str(framerate),
            "-start_number", str(start_num),
            "-i", input_path,
        ])

    num_inputs = len(valid_layers)

    # Build overlay filter chain
    # [0] = background, [1] = next layer, ... [N-1] = foreground
    if num_inputs == 2:
        filter_complex = "[0:v][1:v]overlay=0:0:format=auto"
    else:
        parts = []
        for i in range(1, num_inputs):
            if i == 1:
                parts.append(f"[0:v][1:v]overlay=0:0:format=auto[tmp{i}]")
            elif i == num_inputs - 1:
                parts.append(f"[tmp{i-1}][{i}:v]overlay=0:0:format=auto")
            else:
                parts.append(f"[tmp{i-1}][{i}:v]overlay=0:0:format=auto[tmp{i}]")
        filter_complex = ";".join(parts)

    composed_name = f"{output_path.name}_composed.mp4"
    composed_path = str(output_path / composed_name)

    cmd.extend([
        "-filter_complex", filter_complex,
        "-frames:v", str(min_frames),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "18",
        composed_path,
    ])

    if on_output:
        on_output(f"[ffmpeg] Compositing {num_inputs} layers ({min_frames} frames @ {framerate}fps)...")
        on_output(f"[ffmpeg] Order (bottom to top): {' -> '.join(n for n, _, _, _, _ in valid_layers)}")
        # Log full command for debugging
        cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        on_output(f"[ffmpeg] Command: {cmd_str}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0:
            if on_output:
                on_output(f"[ffmpeg] Composition completed: {composed_path}")
            return composed_path
        else:
            error = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
            if on_output:
                on_output(f"[ffmpeg] Composition FAILED (exit {result.returncode}): {error}")
            return None
    except Exception as e:
        if on_output:
            on_output(f"[ffmpeg] ERROR: {e}")
        return None
