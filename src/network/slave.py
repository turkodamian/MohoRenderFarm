"""Slave client for distributed rendering."""
import socket
import threading
import time
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

        # Callbacks
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None
        self.on_job_started: Optional[Callable[[RenderJob], None]] = None
        self.on_job_completed: Optional[Callable[[RenderJob], None]] = None
        self.on_output: Optional[Callable[[str], None]] = None
        self.on_status_changed: Optional[Callable[[str], None]] = None

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
                requests.post(
                    f"{self.master_url}/api/heartbeat",
                    json={
                        "port": self.slave_port,
                        "status": status,
                        "active_jobs": active_count,
                    },
                    timeout=5,
                )
            except Exception:
                pass
            time.sleep(10)

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

        # Report completion
        success = job.status == RenderStatus.COMPLETED.value
        try:
            requests.post(
                f"{self.master_url}/api/job_complete",
                json={
                    "port": self.slave_port,
                    "job_id": job.id,
                    "success": success,
                    "error": job.error_message,
                },
                timeout=10,
            )
        except Exception as e:
            if self.on_output:
                self.on_output(f"Error reporting job completion: {e}")

        if self.on_job_completed:
            self.on_job_completed(job)
        if self.on_status_changed:
            with self._lock:
                count = len(self._active_renders)
            status = f"rendering ({count} active)" if count > 0 else "idle"
            self.on_status_changed(status)
