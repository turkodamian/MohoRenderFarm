"""Slave client for distributed rendering."""
import socket
import threading
import time
from typing import Optional, Callable
import requests
from src.moho_renderer import RenderJob, MohoRenderer, RenderStatus


class SlaveClient:
    """Connects to a master server and processes render jobs."""

    def __init__(self, master_host: str, master_port: int, moho_path: str, slave_port: int = 0):
        self.master_host = master_host
        self.master_port = master_port
        self.moho_path = moho_path
        self.slave_port = slave_port
        self.hostname = socket.gethostname()
        self._running = False
        self._thread = None
        self._heartbeat_thread = None
        self._renderer: Optional[MohoRenderer] = None
        self._current_job: Optional[RenderJob] = None

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

    def start(self):
        """Start the slave client."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop(self):
        """Stop the slave client."""
        self._running = False
        if self._renderer:
            self._renderer.cancel()
        if self._thread:
            self._thread.join(timeout=10)

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
                status = "rendering" if self._current_job else "idle"
                requests.post(
                    f"{self.master_url}/api/heartbeat",
                    json={"port": self.slave_port, "status": status},
                    timeout=5,
                )
            except Exception:
                pass
            time.sleep(10)

    def _worker_loop(self):
        """Main worker loop: request and process jobs."""
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
                        self._process_job(job)
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
                    self.on_output("Lost connection to master, reconnecting...")
                time.sleep(5)
            except Exception as e:
                if self.on_output:
                    self.on_output(f"Worker error: {e}")
                time.sleep(5)

    def _process_job(self, job: RenderJob):
        """Process a single render job."""
        self._current_job = job
        if self.on_job_started:
            self.on_job_started(job)
        if self.on_output:
            self.on_output(f"Processing job: {job.project_name}")
        if self.on_status_changed:
            self.on_status_changed("rendering")

        self._renderer = MohoRenderer(self.moho_path)
        self._renderer.render(
            job,
            on_output=self.on_output,
        )

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
            self.on_status_changed("idle")

        self._current_job = None
        self._renderer = None
