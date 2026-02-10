"""Render queue management system."""
import json
import threading
import time
from pathlib import Path
from typing import Optional, Callable, List
from src.moho_renderer import RenderJob, RenderStatus, MohoRenderer


class RenderQueue:
    """Manages a queue of render jobs with sequential execution."""

    def __init__(self, moho_path: str):
        self.jobs: List[RenderJob] = []
        self.moho_path = moho_path
        self._renderer: Optional[MohoRenderer] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._current_job: Optional[RenderJob] = None
        self._paused = False
        self._lock = threading.Lock()

        # Callbacks
        self.on_job_started: Optional[Callable[[RenderJob], None]] = None
        self.on_job_completed: Optional[Callable[[RenderJob], None]] = None
        self.on_job_failed: Optional[Callable[[RenderJob], None]] = None
        self.on_queue_completed: Optional[Callable[[], None]] = None
        self.on_output: Optional[Callable[[str], None]] = None
        self.on_progress: Optional[Callable[[RenderJob, float], None]] = None
        self.on_queue_changed: Optional[Callable[[], None]] = None

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
        """Start processing the queue."""
        if self._running:
            return
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._process_queue, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop processing and cancel current render."""
        self._running = False
        self._paused = False
        if self._renderer:
            self._renderer.cancel()
        if self._thread:
            self._thread.join(timeout=10)

    def pause(self):
        """Pause queue processing (finishes current job)."""
        self._paused = True

    def resume(self):
        """Resume queue processing."""
        self._paused = False
        if not self._running:
            self.start()

    def cancel_current(self):
        """Cancel only the current rendering job."""
        if self._renderer and self._current_job:
            self._renderer.cancel()

    @property
    def is_running(self):
        return self._running

    @property
    def is_paused(self):
        return self._paused

    @property
    def current_job(self):
        return self._current_job

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

    def _process_queue(self):
        """Process jobs in the queue sequentially."""
        self._renderer = MohoRenderer(self.moho_path)

        while self._running:
            if self._paused:
                time.sleep(0.5)
                continue

            next_job = None
            with self._lock:
                for job in self.jobs:
                    if job.status == RenderStatus.PENDING.value:
                        next_job = job
                        break

            if next_job is None:
                self._running = False
                if self.on_queue_completed:
                    self.on_queue_completed()
                break

            self._current_job = next_job

            if self.on_job_started:
                self.on_job_started(next_job)

            def _on_progress(progress):
                next_job.progress = progress
                if self.on_progress:
                    self.on_progress(next_job, progress)

            self._renderer.render(
                next_job,
                on_output=self.on_output,
                on_complete=None,
                on_progress=_on_progress,
            )

            self._current_job = None

            if next_job.status == RenderStatus.COMPLETED.value:
                if self.on_job_completed:
                    self.on_job_completed(next_job)
            elif next_job.status == RenderStatus.FAILED.value:
                if self.on_job_failed:
                    self.on_job_failed(next_job)

            if self.on_queue_changed:
                self.on_queue_changed()

        self._renderer = None
        self._current_job = None

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
