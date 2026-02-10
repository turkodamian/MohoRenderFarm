"""Core Moho CLI rendering engine wrapper."""
import subprocess
import os
import time
import threading
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Callable


class RenderStatus(Enum):
    PENDING = "pending"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RenderJob:
    """Represents a single render job with all Moho CLI options."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_file: str = ""
    output_path: str = ""
    format: str = "MP4"
    options: str = "MP4 (MPEG4-AAC)"
    start_frame: Optional[int] = None
    end_frame: Optional[int] = None
    verbose: bool = True
    quiet: bool = False
    log_file: str = ""
    multithread: Optional[bool] = None
    halfsize: Optional[bool] = None
    halffps: Optional[bool] = None
    shapefx: Optional[bool] = None
    layerfx: Optional[bool] = None
    fewparticles: Optional[bool] = None
    layercomp: str = ""
    aa: Optional[bool] = None
    extrasmooth: Optional[bool] = None
    premultiply: Optional[bool] = None
    ntscsafe: Optional[bool] = None
    addformatsuffix: Optional[bool] = None
    addlayercompsuffix: Optional[bool] = None
    createfolderforlayercomps: Optional[bool] = None
    videocodec: Optional[int] = None
    quality: Optional[int] = None
    depth: Optional[int] = None
    # Runtime state
    status: str = RenderStatus.PENDING.value
    progress: float = 0.0
    error_message: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    assigned_slave: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @property
    def project_name(self):
        return Path(self.project_file).stem if self.project_file else ""

    @property
    def elapsed_time(self):
        if self.start_time is None:
            return 0
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    @property
    def elapsed_str(self):
        elapsed = self.elapsed_time
        mins, secs = divmod(int(elapsed), 60)
        hours, mins = divmod(mins, 60)
        if hours:
            return f"{hours}h {mins}m {secs}s"
        if mins:
            return f"{mins}m {secs}s"
        return f"{secs}s"


class MohoRenderer:
    """Wraps the Moho CLI for rendering."""

    def __init__(self, moho_path: str):
        self.moho_path = moho_path
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False

    def build_command(self, job: RenderJob) -> list:
        """Build the Moho command-line arguments from a RenderJob."""
        cmd = [self.moho_path, "-r", job.project_file]

        if job.format:
            cmd.extend(["-f", job.format])

        if job.options:
            cmd.extend(["-options", job.options])

        if job.output_path:
            cmd.extend(["-o", job.output_path])

        if job.start_frame is not None:
            cmd.extend(["-start", str(job.start_frame)])

        if job.end_frame is not None:
            cmd.extend(["-end", str(job.end_frame)])

        if job.verbose and not job.quiet:
            cmd.append("-v")

        if job.quiet:
            cmd.append("-q")

        if job.log_file:
            cmd.extend(["-log", job.log_file])

        # Boolean render options
        bool_opts = {
            "-multithread": job.multithread,
            "-halfsize": job.halfsize,
            "-halffps": job.halffps,
            "-shapefx": job.shapefx,
            "-layerfx": job.layerfx,
            "-fewparticles": job.fewparticles,
            "-aa": job.aa,
            "-extrasmooth": job.extrasmooth,
            "-premultiply": job.premultiply,
            "-ntscsafe": job.ntscsafe,
            "-addformatsuffix": job.addformatsuffix,
            "-addlayercompsuffix": job.addlayercompsuffix,
            "-createfolderforlayercomps": job.createfolderforlayercomps,
        }
        for flag, value in bool_opts.items():
            if value is not None:
                cmd.extend([flag, "yes" if value else "no"])

        if job.layercomp:
            cmd.extend(["-layercomp", job.layercomp])

        if job.videocodec is not None:
            cmd.extend(["-videocodec", str(job.videocodec)])

        if job.quality is not None:
            cmd.extend(["-quality", str(job.quality)])

        if job.depth is not None:
            cmd.extend(["-depth", str(job.depth)])

        return cmd

    def render(self, job: RenderJob,
               on_output: Optional[Callable[[str], None]] = None,
               on_complete: Optional[Callable[[RenderJob], None]] = None,
               on_progress: Optional[Callable[[float], None]] = None) -> RenderJob:
        """Execute a render job synchronously."""
        self._cancelled = False
        job.status = RenderStatus.RENDERING.value
        job.start_time = time.time()
        job.error_message = ""

        cmd = self.build_command(job)

        # Ensure output directory exists
        if job.output_path:
            out_path = Path(job.output_path)
            if out_path.suffix:  # It's a file path
                out_path.parent.mkdir(parents=True, exist_ok=True)
            else:  # It's a directory
                out_path.mkdir(parents=True, exist_ok=True)

        # Create a log file for this job if not specified
        log_path = job.log_file
        if not log_path and job.verbose:
            from src.config import CONFIG_DIR
            log_dir = CONFIG_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = str(log_dir / f"render_{job.id}.log")
            # Add log to command if not already there
            if "-log" not in cmd:
                cmd.extend(["-log", log_path])

        if on_output:
            on_output(f"[{job.id}] Starting render: {job.project_name}")
            on_output(f"[{job.id}] Command: {' '.join(cmd)}")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            # Monitor log file for progress if verbose
            if log_path:
                monitor = LogMonitor(log_path, on_output, on_progress)
                monitor.start()

            stdout, stderr = self._process.communicate()
            return_code = self._process.returncode

            if log_path:
                monitor.stop()

            if self._cancelled:
                job.status = RenderStatus.CANCELLED.value
                if on_output:
                    on_output(f"[{job.id}] Render cancelled")
            elif return_code == 0:
                job.status = RenderStatus.COMPLETED.value
                job.progress = 100.0
                if on_output:
                    on_output(f"[{job.id}] Render completed successfully")
            else:
                job.status = RenderStatus.FAILED.value
                error = stderr.decode("utf-8", errors="replace").strip() if stderr else f"Exit code: {return_code}"
                job.error_message = error
                if on_output:
                    on_output(f"[{job.id}] Render FAILED: {error}")

        except FileNotFoundError:
            job.status = RenderStatus.FAILED.value
            job.error_message = f"Moho executable not found: {self.moho_path}"
            if on_output:
                on_output(f"[{job.id}] ERROR: {job.error_message}")
        except Exception as e:
            job.status = RenderStatus.FAILED.value
            job.error_message = str(e)
            if on_output:
                on_output(f"[{job.id}] ERROR: {e}")
        finally:
            job.end_time = time.time()
            self._process = None
            if on_complete:
                on_complete(job)

        return job

    def cancel(self):
        """Cancel the current render."""
        self._cancelled = True
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()


class LogMonitor:
    """Monitors a Moho log file for progress updates."""

    def __init__(self, log_path: str,
                 on_output: Optional[Callable[[str], None]] = None,
                 on_progress: Optional[Callable[[float], None]] = None):
        self.log_path = log_path
        self.on_output = on_output
        self.on_progress = on_progress
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _monitor(self):
        last_size = 0
        while self._running:
            try:
                if os.path.exists(self.log_path):
                    with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_size)
                        new_content = f.read()
                        if new_content:
                            last_size = f.tell()
                            for line in new_content.strip().split("\n"):
                                if line.strip():
                                    if self.on_output:
                                        self.on_output(line.strip())
                                    self._parse_progress(line)
            except (IOError, OSError):
                pass
            time.sleep(0.5)

    def _parse_progress(self, line: str):
        """Try to extract progress from Moho log output.
        Moho outputs: 'Frame 1 (1/5)  X.XX secs/frame  Y.YY secs remaining'
        """
        if self.on_progress is None:
            return
        line_stripped = line.strip()
        # Match pattern: Frame N (current/total)
        if line_stripped.startswith("Frame "):
            try:
                # Extract the (current/total) part
                paren_start = line_stripped.index("(")
                paren_end = line_stripped.index(")")
                fraction = line_stripped[paren_start + 1:paren_end]
                parts = fraction.split("/")
                if len(parts) == 2:
                    current = int(parts[0])
                    total = int(parts[1])
                    if total > 0:
                        self.on_progress((current / total) * 100.0)
            except (ValueError, IndexError):
                pass
