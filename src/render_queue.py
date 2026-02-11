"""Render queue management system."""
import json
import threading
import time
from pathlib import Path
from typing import Optional, Callable, List, Dict, Tuple
from src.moho_renderer import RenderJob, RenderStatus, MohoRenderer


class RenderQueue:
    """Manages a queue of render jobs with concurrent execution."""

    def __init__(self, moho_path: str, max_concurrent: int = 1):
        self.jobs: List[RenderJob] = []
        self.moho_path = moho_path
        self._max_concurrent = max(1, max_concurrent)
        self._running = False
        self._paused = False
        self._lock = threading.Lock()

        # Multi-worker state
        self._workers: List[threading.Thread] = []
        self._active_renders: Dict[int, Tuple[MohoRenderer, RenderJob]] = {}
        self._workers_done = 0

        # Callbacks
        self.on_job_started: Optional[Callable[[RenderJob], None]] = None
        self.on_job_completed: Optional[Callable[[RenderJob], None]] = None
        self.on_job_failed: Optional[Callable[[RenderJob], None]] = None
        self.on_queue_completed: Optional[Callable[[], None]] = None
        self.on_output: Optional[Callable[[str], None]] = None
        self.on_progress: Optional[Callable[[RenderJob, float], None]] = None
        self.on_queue_changed: Optional[Callable[[], None]] = None

    @property
    def max_concurrent(self):
        return self._max_concurrent

    @max_concurrent.setter
    def max_concurrent(self, value: int):
        self._max_concurrent = max(1, value)

    def add_job(self, job: RenderJob) -> RenderJob:
        """Add a job to the queue."""
        with self._lock:
            self.jobs.append(job)
        if self.on_queue_changed:
            self.on_queue_changed()
        return job

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the queue by ID."""
        with self._lock:
            for i, job in enumerate(self.jobs):
                if job.id == job_id:
                    if job.status == RenderStatus.RENDERING.value:
                        return False  # Can't remove while rendering
                    self.jobs.pop(i)
                    if self.on_queue_changed:
                        self.on_queue_changed()
                    return True
        return False

    def move_job(self, job_id: str, direction: int) -> bool:
        """Move a job up (-1) or down (+1) in the queue."""
        with self._lock:
            for i, job in enumerate(self.jobs):
                if job.id == job_id:
                    new_idx = i + direction
                    if 0 <= new_idx < len(self.jobs):
                        self.jobs[i], self.jobs[new_idx] = self.jobs[new_idx], self.jobs[i]
                        if self.on_queue_changed:
                            self.on_queue_changed()
                        return True
        return False

    def clear_completed(self):
        """Remove all completed/failed/cancelled jobs."""
        with self._lock:
            self.jobs = [j for j in self.jobs if j.status in
                         (RenderStatus.PENDING.value, RenderStatus.RENDERING.value)]
        if self.on_queue_changed:
            self.on_queue_changed()

    def clear_all(self):
        """Remove all non-rendering jobs."""
        with self._lock:
            self.jobs = [j for j in self.jobs if j.status == RenderStatus.RENDERING.value]
        if self.on_queue_changed:
            self.on_queue_changed()

    def get_job(self, job_id: str) -> Optional[RenderJob]:
        """Get a job by ID."""
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def get_pending_jobs(self) -> List[RenderJob]:
        """Get all pending jobs."""
        return [j for j in self.jobs if j.status == RenderStatus.PENDING.value]

    def start(self):
        """Start processing the queue with concurrent workers."""
        if self._running:
            return
        self._running = True
        self._paused = False
        self._workers_done = 0
        self._workers = []
        for i in range(self._max_concurrent):
            t = threading.Thread(target=self._worker_func, args=(i,), daemon=True)
            self._workers.append(t)
            t.start()

    def stop(self):
        """Stop processing and cancel all active renders."""
        self._running = False
        self._paused = False
        with self._lock:
            for renderer, _ in self._active_renders.values():
                renderer.cancel()
        for t in self._workers:
            t.join(timeout=10)
        self._workers = []

    def pause(self):
        """Pause queue processing (finishes current jobs)."""
        self._paused = True

    def resume(self):
        """Resume queue processing."""
        self._paused = False
        if not self._running:
            self.start()

    def cancel_current(self):
        """Cancel all currently rendering jobs."""
        with self._lock:
            for renderer, _ in list(self._active_renders.values()):
                renderer.cancel()

    @property
    def is_running(self):
        return self._running

    @property
    def is_paused(self):
        return self._paused

    @property
    def current_jobs(self) -> List[RenderJob]:
        """Return list of all currently rendering jobs."""
        with self._lock:
            return [job for _, job in self._active_renders.values()]

    @property
    def current_job(self) -> Optional[RenderJob]:
        """Return the first currently rendering job (backward compat)."""
        with self._lock:
            if self._active_renders:
                _, job = next(iter(self._active_renders.values()))
                return job
        return None

    @property
    def total_jobs(self):
        return len(self.jobs)

    @property
    def pending_count(self):
        return len([j for j in self.jobs if j.status == RenderStatus.PENDING.value])

    @property
    def completed_count(self):
        return len([j for j in self.jobs if j.status == RenderStatus.COMPLETED.value])

    @property
    def failed_count(self):
        return len([j for j in self.jobs if j.status == RenderStatus.FAILED.value])

    def _worker_func(self, worker_id: int):
        """Worker thread: grab pending jobs and render them."""
        while self._running:
            if self._paused:
                time.sleep(0.5)
                continue

            # Find next pending job
            next_job = None
            with self._lock:
                for job in self.jobs:
                    if job.status == RenderStatus.PENDING.value:
                        next_job = job
                        # Mark as rendering immediately to prevent other workers from grabbing it
                        next_job.status = RenderStatus.RENDERING.value
                        break

            if next_job is None:
                # No pending jobs left, worker exits
                break

            # Create renderer for this worker
            renderer = MohoRenderer(self.moho_path)
            with self._lock:
                self._active_renders[worker_id] = (renderer, next_job)

            if self.on_job_started:
                self.on_job_started(next_job)

            def _on_progress(progress, _job=next_job):
                _job.progress = progress
                if self.on_progress:
                    self.on_progress(_job, progress)

            renderer.render(
                next_job,
                on_output=self.on_output,
                on_complete=None,
                on_progress=_on_progress,
            )

            with self._lock:
                self._active_renders.pop(worker_id, None)

            # Post-render: auto-compose layer comps with ffmpeg
            if (next_job.status == RenderStatus.COMPLETED.value
                    and next_job.compose_layers and next_job.layercomp):
                try:
                    from src.ffmpeg_compose import compose_layer_comps
                    out_dir = Path(next_job.output_path).parent if next_job.output_path else Path(next_job.project_file).parent
                    if self.on_output:
                        self.on_output(f"[{next_job.id}] Starting ffmpeg layer composition...")
                    compose_layer_comps(str(out_dir), on_output=self.on_output)
                except Exception as e:
                    if self.on_output:
                        self.on_output(f"[{next_job.id}] FFmpeg compose error: {e}")

            if next_job.status == RenderStatus.COMPLETED.value:
                if self.on_job_completed:
                    self.on_job_completed(next_job)
            elif next_job.status == RenderStatus.FAILED.value:
                if self.on_job_failed:
                    self.on_job_failed(next_job)

            if self.on_queue_changed:
                self.on_queue_changed()

        # Worker exiting — check if all workers are done
        all_done = False
        with self._lock:
            self._workers_done += 1
            if self._workers_done >= len(self._workers):
                # All workers finished
                pending = any(j.status == RenderStatus.PENDING.value for j in self.jobs)
                if not pending:
                    self._running = False
                    all_done = True

        if all_done and self.on_queue_completed:
            self.on_queue_completed()

    def save_queue(self, filepath: str):
        """Save the queue to a JSON file."""
        data = {
            "version": "1.0",
            "jobs": [job.to_dict() for job in self.jobs],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_queue(self, filepath: str, append: bool = False):
        """Load a queue from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not append:
            with self._lock:
                self.jobs = [j for j in self.jobs if j.status == RenderStatus.RENDERING.value]

        for job_data in data.get("jobs", []):
            job = RenderJob.from_dict(job_data)
            # Reset status for loaded jobs
            if job.status not in (RenderStatus.RENDERING.value,):
                job.status = RenderStatus.PENDING.value
                job.progress = 0.0
                job.error_message = ""
                job.start_time = None
                job.end_time = None
            with self._lock:
                self.jobs.append(job)

        if self.on_queue_changed:
            self.on_queue_changed()

    def duplicate_job(self, job_id: str) -> Optional[RenderJob]:
        """Duplicate a job in the queue."""
        original = self.get_job(job_id)
        if original is None:
            return None
        new_job = RenderJob.from_dict(original.to_dict())
        new_job.id = RenderJob().id  # Generate new ID
        new_job.status = RenderStatus.PENDING.value
        new_job.progress = 0.0
        new_job.error_message = ""
        new_job.start_time = None
        new_job.end_time = None
        with self._lock:
            idx = self.jobs.index(original)
            self.jobs.insert(idx + 1, new_job)
        if self.on_queue_changed:
            self.on_queue_changed()
        return new_job

    def retry_job(self, job_id: str) -> bool:
        """Reset a failed/cancelled job to pending."""
        job = self.get_job(job_id)
        if job and job.status in (RenderStatus.FAILED.value, RenderStatus.CANCELLED.value, RenderStatus.COMPLETED.value):
            job.status = RenderStatus.PENDING.value
            job.progress = 0.0
            job.error_message = ""
            job.start_time = None
            job.end_time = None
            if self.on_queue_changed:
                self.on_queue_changed()
            return True
        return False
