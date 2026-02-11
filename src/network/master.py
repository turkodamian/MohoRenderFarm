"""Master server for distributed rendering."""
import json
import threading
import time
import socket
from typing import Optional, Callable, Dict, List
from flask import Flask, request, jsonify
from src.moho_renderer import RenderJob, RenderStatus


class SlaveInfo:
    """Information about a connected slave node."""
    def __init__(self, hostname: str, ip: str, port: int):
        self.hostname = hostname
        self.ip = ip
        self.port = port
        self.status = "idle"  # idle, rendering, offline
        self.current_job_id = ""
        self.last_heartbeat = time.time()
        self.jobs_completed = 0
        self.jobs_failed = 0

    @property
    def address(self):
        return f"{self.ip}:{self.port}"

    @property
    def is_alive(self):
        return (time.time() - self.last_heartbeat) < 30

    def to_dict(self):
        return {
            "hostname": self.hostname,
            "ip": self.ip,
            "port": self.port,
            "status": self.status if self.is_alive else "offline",
            "current_job_id": self.current_job_id,
            "last_heartbeat": self.last_heartbeat,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
        }


class MasterServer:
    """HTTP-based master server that distributes render jobs to slaves."""

    def __init__(self, port: int = 5580):
        self.port = port
        self.slaves: Dict[str, SlaveInfo] = {}
        self.pending_jobs: List[RenderJob] = []
        self.active_jobs: Dict[str, RenderJob] = {}  # slave_address -> job
        self.reserved_jobs: Dict[str, RenderJob] = {}  # slave_address -> reserved job
        self.completed_jobs: List[RenderJob] = []  # history of completed/failed jobs
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._distributor_thread = None

        # Callbacks
        self.on_slave_connected: Optional[Callable[[SlaveInfo], None]] = None
        self.on_slave_disconnected: Optional[Callable[[SlaveInfo], None]] = None
        self.on_job_assigned: Optional[Callable[[RenderJob, SlaveInfo], None]] = None
        self.on_job_completed: Optional[Callable[[RenderJob, SlaveInfo], None]] = None
        self.on_job_failed: Optional[Callable[[RenderJob, SlaveInfo], None]] = None
        self.on_output: Optional[Callable[[str], None]] = None
        self.on_farm_queue_changed: Optional[Callable[[], None]] = None

        self._app = Flask(__name__)
        self._setup_routes()

    def _notify_queue_changed(self):
        """Fire the queue-changed callback (thread-safe for GUI signal emission)."""
        if self.on_farm_queue_changed:
            self.on_farm_queue_changed()

    def _setup_routes(self):
        app = self._app

        @app.route("/api/register", methods=["POST"])
        def register_slave():
            data = request.json
            hostname = data.get("hostname", "unknown")
            ip = request.remote_addr
            port = data.get("port", 0)
            key = f"{ip}:{port}"

            with self._lock:
                if key not in self.slaves:
                    slave = SlaveInfo(hostname, ip, port)
                    self.slaves[key] = slave
                    if self.on_slave_connected:
                        self.on_slave_connected(slave)
                    if self.on_output:
                        self.on_output(f"Slave connected: {hostname} ({key})")
                else:
                    self.slaves[key].last_heartbeat = time.time()
                    self.slaves[key].hostname = hostname
                    if self.slaves[key].status == "offline":
                        self.slaves[key].status = "idle"
                        if self.on_slave_connected:
                            self.on_slave_connected(self.slaves[key])
                        if self.on_output:
                            self.on_output(f"Slave reconnected: {hostname} ({key})")

            return jsonify({"status": "registered", "address": key})

        @app.route("/api/heartbeat", methods=["POST"])
        def heartbeat():
            data = request.json
            ip = request.remote_addr
            port = data.get("port", 0)
            key = f"{ip}:{port}"

            with self._lock:
                if key in self.slaves:
                    self.slaves[key].last_heartbeat = time.time()
                    self.slaves[key].status = data.get("status", "idle")

            return jsonify({"status": "ok"})

        @app.route("/api/get_job", methods=["GET"])
        def get_job():
            ip = request.remote_addr
            port = request.args.get("port", 0, type=int)
            key = f"{ip}:{port}"

            with self._lock:
                if key not in self.slaves:
                    return jsonify({"job": None, "error": "not registered"}), 403

                self.slaves[key].last_heartbeat = time.time()

                # Check for a manually reserved job first
                job = self.reserved_jobs.pop(key, None)

                # Fall back to FIFO from pending queue
                if job is None and self.pending_jobs:
                    job = self.pending_jobs.pop(0)

                if job:
                    job.status = RenderStatus.RENDERING.value
                    job.assigned_slave = key
                    job.start_time = time.time()
                    self.active_jobs[key] = job
                    self.slaves[key].status = "rendering"
                    self.slaves[key].current_job_id = job.id

                    if self.on_job_assigned:
                        self.on_job_assigned(job, self.slaves[key])
                    if self.on_output:
                        self.on_output(f"Job assigned: {job.project_name} [{job.id}] -> {self.slaves[key].hostname}")

                    self._notify_queue_changed()
                    return jsonify({"job": job.to_dict()})

            return jsonify({"job": None})

        @app.route("/api/job_complete", methods=["POST"])
        def job_complete():
            data = request.json
            ip = request.remote_addr
            port = data.get("port", 0)
            key = f"{ip}:{port}"
            job_id = data.get("job_id", "")
            success = data.get("success", False)
            error = data.get("error", "")

            with self._lock:
                if key in self.active_jobs:
                    job = self.active_jobs.pop(key)
                    job.end_time = time.time()
                    if success:
                        job.status = RenderStatus.COMPLETED.value
                        job.progress = 100.0
                        if key in self.slaves:
                            self.slaves[key].jobs_completed += 1
                        if self.on_job_completed:
                            self.on_job_completed(job, self.slaves.get(key))
                        if self.on_output:
                            elapsed = job.elapsed_str
                            slave_name = self.slaves.get(key, SlaveInfo('?', '?', 0)).hostname
                            self.on_output(f"Job completed: {job.project_name} [{job_id}] on {slave_name} ({elapsed})")
                    else:
                        job.status = RenderStatus.FAILED.value
                        job.error_message = error
                        if key in self.slaves:
                            self.slaves[key].jobs_failed += 1
                        if self.on_job_failed:
                            self.on_job_failed(job, self.slaves.get(key))
                        if self.on_output:
                            slave_name = self.slaves.get(key, SlaveInfo('?', '?', 0)).hostname
                            self.on_output(f"Job FAILED: {job.project_name} [{job_id}] on {slave_name}: {error}")

                    self.completed_jobs.append(job)

                if key in self.slaves:
                    self.slaves[key].status = "idle"
                    self.slaves[key].current_job_id = ""

            self._notify_queue_changed()
            return jsonify({"status": "ok"})

        @app.route("/api/status", methods=["GET"])
        def status():
            with self._lock:
                return jsonify({
                    "slaves": {k: v.to_dict() for k, v in self.slaves.items()},
                    "pending_jobs": len(self.pending_jobs),
                    "active_jobs": len(self.active_jobs),
                    "reserved_jobs": len(self.reserved_jobs),
                    "completed_jobs": len(self.completed_jobs),
                })

        @app.route("/api/add_job", methods=["POST"])
        def add_job():
            data = request.json
            job = RenderJob.from_dict(data)
            self.add_job(job)
            return jsonify({"status": "added", "job_id": job.id})

        @app.route("/api/queue", methods=["GET"])
        def get_queue():
            with self._lock:
                jobs = [j.to_dict() for j in self.pending_jobs]
                active = {k: v.to_dict() for k, v in self.active_jobs.items()}
                reserved = {k: v.to_dict() for k, v in self.reserved_jobs.items()}
                completed = [j.to_dict() for j in self.completed_jobs]
            return jsonify({
                "pending": jobs,
                "active": active,
                "reserved": reserved,
                "completed": completed,
            })

    def add_job(self, job: RenderJob):
        """Add a job to the distribution queue."""
        with self._lock:
            job.status = RenderStatus.PENDING.value
            self.pending_jobs.append(job)
        if self.on_output:
            self.on_output(f"Job added to farm: {job.project_name} [{job.id}]")
        self._notify_queue_changed()

    def assign_job_to_slave(self, job_id: str, slave_address: str) -> bool:
        """Reserve a pending job for a specific slave (manual assignment)."""
        with self._lock:
            target_job = None
            for i, job in enumerate(self.pending_jobs):
                if job.id == job_id:
                    target_job = self.pending_jobs.pop(i)
                    break
            if target_job is None:
                return False
            if slave_address not in self.slaves or not self.slaves[slave_address].is_alive:
                self.pending_jobs.insert(0, target_job)
                return False
            self.reserved_jobs[slave_address] = target_job
        if self.on_output:
            slave_name = self.slaves.get(slave_address, SlaveInfo('?', '?', 0)).hostname
            self.on_output(f"Job reserved: {target_job.project_name} [{job_id}] -> {slave_name}")
        self._notify_queue_changed()
        return True

    def cancel_job(self, job_id: str) -> Optional[RenderJob]:
        """Cancel a pending or reserved job. Returns the job if found."""
        with self._lock:
            for i, job in enumerate(self.pending_jobs):
                if job.id == job_id:
                    job = self.pending_jobs.pop(i)
                    job.status = RenderStatus.CANCELLED.value
                    self.completed_jobs.append(job)
                    if self.on_output:
                        self.on_output(f"Job cancelled: {job.project_name} [{job_id}]")
                    self._notify_queue_changed()
                    return job
            for addr, job in list(self.reserved_jobs.items()):
                if job.id == job_id:
                    del self.reserved_jobs[addr]
                    job.status = RenderStatus.CANCELLED.value
                    self.completed_jobs.append(job)
                    if self.on_output:
                        self.on_output(f"Job cancelled: {job.project_name} [{job_id}] (was reserved for {addr})")
                    self._notify_queue_changed()
                    return job
        return None

    def remove_job_from_farm(self, job_id: str) -> Optional[RenderJob]:
        """Remove a pending/reserved job from the farm (to return to local queue)."""
        with self._lock:
            for i, job in enumerate(self.pending_jobs):
                if job.id == job_id:
                    job = self.pending_jobs.pop(i)
                    if self.on_output:
                        self.on_output(f"Job removed from farm: {job.project_name} [{job_id}]")
                    self._notify_queue_changed()
                    return job
            for addr, job in list(self.reserved_jobs.items()):
                if job.id == job_id:
                    del self.reserved_jobs[addr]
                    if self.on_output:
                        self.on_output(f"Job removed from farm: {job.project_name} [{job_id}]")
                    self._notify_queue_changed()
                    return job
        return None

    def get_all_farm_jobs(self):
        """Return all farm jobs grouped by status for GUI display."""
        with self._lock:
            return {
                "pending": list(self.pending_jobs),
                "reserved": list(self.reserved_jobs.values()),
                "active": list(self.active_jobs.values()),
                "completed": list(self.completed_jobs),
            }

    def clear_completed_farm_jobs(self):
        """Clear the completed/failed/cancelled job history."""
        with self._lock:
            count = len(self.completed_jobs)
            self.completed_jobs.clear()
        if self.on_output:
            self.on_output(f"Cleared {count} completed farm jobs")
        self._notify_queue_changed()

    def start(self):
        """Start the master server."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        self._distributor_thread = threading.Thread(target=self._check_slaves, daemon=True)
        self._distributor_thread.start()
        if self.on_output:
            self.on_output(f"Master server started on port {self.port}")

    def stop(self):
        """Stop the master server."""
        self._running = False
        if self.on_output:
            self.on_output("Master server stopped")

    def _run_server(self):
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        try:
            self._app.run(host="0.0.0.0", port=self.port, threaded=True, use_reloader=False)
        except Exception as e:
            if self.on_output:
                self.on_output(f"Master server error: {e}")

    def _check_slaves(self):
        """Periodically check for disconnected slaves."""
        while self._running:
            queue_changed = False
            with self._lock:
                for key, slave in list(self.slaves.items()):
                    if not slave.is_alive and slave.status != "offline":
                        slave.status = "offline"
                        if self.on_slave_disconnected:
                            self.on_slave_disconnected(slave)
                        if self.on_output:
                            self.on_output(f"Slave disconnected: {slave.hostname} ({key})")
                        # Return any active jobs back to queue
                        if key in self.active_jobs:
                            job = self.active_jobs.pop(key)
                            job.status = RenderStatus.PENDING.value
                            job.assigned_slave = ""
                            self.pending_jobs.insert(0, job)
                            queue_changed = True
                            if self.on_output:
                                self.on_output(f"Job returned to queue: {job.project_name} [{job.id}] (slave offline)")
                        # Return any reserved jobs back to queue
                        if key in self.reserved_jobs:
                            job = self.reserved_jobs.pop(key)
                            self.pending_jobs.insert(0, job)
                            queue_changed = True
                            if self.on_output:
                                self.on_output(f"Reserved job returned to queue: {job.project_name} [{job.id}] (slave offline)")
            if queue_changed:
                self._notify_queue_changed()
            time.sleep(10)

    def get_local_ip(self):
        """Get the local IP address for network display."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
