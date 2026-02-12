"""Slave client for distributed rendering."""
import os
import shutil
import socket
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Optional, Callable, Dict, Tuple, List
import requests
from src.moho_renderer import RenderJob, MohoRenderer, RenderStatus


class SlaveClient:
    """Connects to a master server and processes render jobs."""

    def __init__(self, master_host: str, master_port: int, moho_path: str,
                 slave_port: int = 0, max_concurrent: int = 1):
        self.master_host = master_host
        self.master_port = master_port
        self.moho_path = moho_path
        self.slave_port = slave_port
        self.hostname = socket.gethostname()
        self._max_concurrent = max(1, max_concurrent)
        self._running = False
        self._workers: List[threading.Thread] = []
        self._heartbeat_thread = None
        self._lock = threading.Lock()
        self._active_renders: Dict[int, Tuple[MohoRenderer, RenderJob]] = {}
        self.completed_jobs: List[RenderJob] = []
        self._force_update_triggered = False

        # Callbacks
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None
        self.on_job_started: Optional[Callable[[RenderJob], None]] = None
        self.on_job_completed: Optional[Callable[[RenderJob], None]] = None
        self.on_output: Optional[Callable[[str], None]] = None
        self.on_status_changed: Optional[Callable[[str], None]] = None
        self.on_force_update: Optional[Callable[[], None]] = None

    @property
    def master_url(self):
        return f"http://{self.master_host}:{self.master_port}"

    @property
    def is_running(self):
        return self._running

    @property
    def current_jobs(self) -> list:
        """Return list of all currently rendering jobs."""
        with self._lock:
            return [job for _, job in self._active_renders.values()]

    def start(self):
        """Start the slave client with concurrent workers."""
        if self._running:
            return
        self._running = True
        self._workers = []
        for i in range(self._max_concurrent):
            t = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            self._workers.append(t)
            t.start()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop(self):
        """Stop the slave client and cancel all active renders."""
        self._running = False
        with self._lock:
            for renderer, _ in self._active_renders.values():
                renderer.cancel()
        for t in self._workers:
            t.join(timeout=10)
        self._workers = []

    def _register(self) -> bool:
        """Register with the master server."""
        try:
            resp = requests.post(
                f"{self.master_url}/api/register",
                json={"hostname": self.hostname, "port": self.slave_port},
                timeout=5,
            )
            if resp.status_code == 200:
                if self.on_connected:
                    self.on_connected()
                if self.on_output:
                    self.on_output(f"Connected to master at {self.master_host}:{self.master_port}")
                return True
        except requests.ConnectionError:
            if self.on_output:
                self.on_output(f"Cannot connect to master at {self.master_host}:{self.master_port}")
        except Exception as e:
            if self.on_output:
                self.on_output(f"Registration error: {e}")
        return False

    def _heartbeat_loop(self):
        """Send periodic heartbeats to master."""
        while self._running:
            try:
                with self._lock:
                    active_count = len(self._active_renders)
                status = "rendering" if active_count > 0 else "idle"
                resp = requests.post(
                    f"{self.master_url}/api/heartbeat",
                    json={
                        "port": self.slave_port,
                        "status": status,
                        "active_jobs": active_count,
                    },
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for job_id in data.get("cancel_jobs", []):
                        self._cancel_active_job(job_id)
                    if data.get("force_update") and not self._force_update_triggered:
                        self._force_update_triggered = True
                        if self.on_output:
                            self.on_output("Master requested force update, checking...")
                        threading.Thread(target=self._handle_force_update, daemon=True).start()
            except Exception:
                pass
            time.sleep(10)

    def _handle_force_update(self):
        """Check for update, download+stage, then signal GUI to restart."""
        try:
            from src.updater import check_for_update, download_and_stage_update
            from src.config import APP_VERSION

            new_version = check_for_update(APP_VERSION)
            if not new_version:
                if self.on_output:
                    self.on_output("Already up to date, no update needed")
                self._force_update_triggered = False
                return

            if self.on_output:
                self.on_output(f"Update v{new_version} found, downloading...")

            success = download_and_stage_update(
                on_progress=lambda msg: self.on_output(msg) if self.on_output else None
            )

            if success:
                if self.on_output:
                    self.on_output(f"Update v{new_version} staged, restarting...")
                if self.on_force_update:
                    self.on_force_update()
            else:
                if self.on_output:
                    self.on_output("Update download failed")
                self._force_update_triggered = False
        except Exception as e:
            if self.on_output:
                self.on_output(f"Force update error: {e}")
            self._force_update_triggered = False

    def _cancel_active_job(self, job_id: str):
        """Cancel a specific active render by job ID (requested by master)."""
        with self._lock:
            for worker_id, (renderer, job) in self._active_renders.items():
                if job.id == job_id:
                    if self.on_output:
                        self.on_output(f"Cancelling job by master request: {job.project_name}")
                    job.status = RenderStatus.CANCELLED.value
                    renderer.cancel()
                    return

    def _worker_loop(self, worker_id: int):
        """Worker loop: request and process jobs from master."""
        registered = False
        while self._running:
            if not registered:
                registered = self._register()
                if not registered:
                    time.sleep(5)
                    continue

            # Request a job
            try:
                resp = requests.get(
                    f"{self.master_url}/api/get_job",
                    params={"port": self.slave_port},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    job_data = data.get("job")
                    if job_data:
                        job = RenderJob.from_dict(job_data)
                        self._process_job(worker_id, job)
                    else:
                        time.sleep(3)
                elif resp.status_code == 403:
                    registered = False
                    time.sleep(2)
                else:
                    time.sleep(5)
            except requests.ConnectionError:
                registered = False
                if self.on_disconnected:
                    self.on_disconnected()
                if self.on_output:
                    self.on_output(f"Worker {worker_id}: Lost connection to master, reconnecting...")
                time.sleep(5)
            except Exception as e:
                if self.on_output:
                    self.on_output(f"Worker {worker_id} error: {e}")
                time.sleep(5)

    def _process_job(self, worker_id: int, job: RenderJob):
        """Process a single render job."""
        work_dir = None

        # Download project files from master if needed
        if job.farm_files_uploaded:
            work_dir = self._download_and_extract_files(worker_id, job)
            if work_dir is None:
                job.status = RenderStatus.FAILED.value
                job.error_message = "Failed to download project files from master"
                self._report_completion(job)
                self.completed_jobs.append(job)
                if self.on_job_completed:
                    self.on_job_completed(job)
                return

        renderer = MohoRenderer(self.moho_path)
        with self._lock:
            self._active_renders[worker_id] = (renderer, job)

        if self.on_job_started:
            self.on_job_started(job)
        if self.on_output:
            self.on_output(f"Worker {worker_id}: Processing job: {job.project_name}")
        if self.on_status_changed:
            with self._lock:
                count = len(self._active_renders)
            self.on_status_changed(f"rendering ({count} active)")

        renderer.render(
            job,
            on_output=self.on_output,
        )

        with self._lock:
            self._active_renders.pop(worker_id, None)

        # Post-render: auto-compose layer comps with ffmpeg
        if (job.status == RenderStatus.COMPLETED.value
                and job.compose_layers and job.layercomp):
            try:
                from src.ffmpeg_compose import compose_layer_comps
                out_dir = Path(job.output_path).parent if job.output_path else Path(job.project_file).parent
                if self.on_output:
                    self.on_output(f"Worker {worker_id}: Starting ffmpeg layer composition...")
                compose_layer_comps(str(out_dir), on_output=self.on_output,
                                    reverse_order=job.compose_reverse_order)
            except Exception as e:
                if self.on_output:
                    self.on_output(f"Worker {worker_id}: FFmpeg compose error: {e}")

        # Report completion
        self._report_completion(job)

        # Cleanup downloaded files
        if work_dir:
            self._cleanup_work_dir(work_dir, job)

        self.completed_jobs.append(job)

        if self.on_job_completed:
            self.on_job_completed(job)
        if self.on_status_changed:
            with self._lock:
                count = len(self._active_renders)
            status = f"rendering ({count} active)" if count > 0 else "idle"
            self.on_status_changed(status)

    def _report_completion(self, job: RenderJob):
        """Report job completion to master."""
        success = job.status == RenderStatus.COMPLETED.value
        cancelled = job.status == RenderStatus.CANCELLED.value
        try:
            requests.post(
                f"{self.master_url}/api/job_complete",
                json={
                    "port": self.slave_port,
                    "job_id": job.id,
                    "success": success,
                    "cancelled": cancelled,
                    "error": job.error_message,
                },
                timeout=10,
            )
        except Exception as e:
            if self.on_output:
                self.on_output(f"Error reporting job completion: {e}")

    def _download_and_extract_files(self, worker_id: int, job: RenderJob):
        """Download project bundle from master and extract to temp dir."""
        work_dir = Path(tempfile.mkdtemp(prefix=f"moho_farm_{job.id}_"))
        zip_path = work_dir / f"{job.id}.zip"

        try:
            if self.on_output:
                self.on_output(f"Worker {worker_id}: Downloading files for {job.project_name}...")

            resp = requests.get(
                f"{self.master_url}/api/download_files/{job.id}",
                timeout=300, stream=True,
            )
            if resp.status_code != 200:
                if self.on_output:
                    self.on_output(f"Worker {worker_id}: File download failed: HTTP {resp.status_code}")
                shutil.rmtree(str(work_dir), ignore_errors=True)
                return None

            with open(str(zip_path), "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)

            size_mb = zip_path.stat().st_size / (1024 * 1024)

            with zipfile.ZipFile(str(zip_path), "r") as zf:
                zf.extractall(str(work_dir))
            zip_path.unlink()

            # Rewrite job project path to extracted location
            original_name = job.farm_original_project or Path(job.project_file).name
            new_project = work_dir / original_name
            if new_project.exists():
                job.project_file = str(new_project)

            if self.on_output:
                self.on_output(f"Worker {worker_id}: Files ready ({size_mb:.1f} MB) in {work_dir}")

            return work_dir
        except Exception as e:
            if self.on_output:
                self.on_output(f"Worker {worker_id}: Download error: {e}")
            shutil.rmtree(str(work_dir), ignore_errors=True)
            return None

    def _cleanup_work_dir(self, work_dir, job: RenderJob):
        """Clean up temp directory and request master cleanup."""
        try:
            shutil.rmtree(str(work_dir), ignore_errors=True)
        except Exception:
            pass
        try:
            requests.delete(
                f"{self.master_url}/api/cleanup_files/{job.id}",
                timeout=10,
            )
        except Exception:
            pass

    def submit_job(self, job: RenderJob, bundle_path: str = "") -> bool:
        """Submit a job to the master for rendering by the farm.

        If bundle_path is provided, uploads the file bundle first.
        Returns True if the master accepted the job.
        """
        # Upload file bundle if provided
        if bundle_path and os.path.exists(bundle_path):
            try:
                if self.on_output:
                    size_mb = os.path.getsize(bundle_path) / (1024 * 1024)
                    self.on_output(f"Uploading files for {job.project_name} ({size_mb:.1f} MB)...")
                with open(bundle_path, "rb") as f:
                    resp = requests.post(
                        f"{self.master_url}/api/upload_files/{job.id}",
                        files={"bundle": (f"{job.id}.zip", f, "application/zip")},
                        timeout=300,
                    )
                if resp.status_code != 200:
                    if self.on_output:
                        self.on_output(f"File upload failed: HTTP {resp.status_code}")
                    return False
                if self.on_output:
                    self.on_output(f"Files uploaded for {job.project_name}")
            except Exception as e:
                if self.on_output:
                    self.on_output(f"File upload error: {e}")
                return False
            finally:
                try:
                    os.unlink(bundle_path)
                except OSError:
                    pass

        # Submit job metadata
        try:
            resp = requests.post(
                f"{self.master_url}/api/add_job",
                json=job.to_dict(),
                timeout=10,
            )
            if resp.status_code == 200:
                if self.on_output:
                    self.on_output(f"Submitted job to master: {job.project_name}")
                return True
            else:
                if self.on_output:
                    self.on_output(f"Master rejected job: HTTP {resp.status_code}")
                return False
        except requests.ConnectionError:
            if self.on_output:
                self.on_output("Cannot submit job: not connected to master")
            return False
        except Exception as e:
            if self.on_output:
                self.on_output(f"Error submitting job: {e}")
            return False
