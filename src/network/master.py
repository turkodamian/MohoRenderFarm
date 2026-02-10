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

        self._app = Flask(__name__)
        self._setup_routes()

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

                if self.pending_jobs:
                    job = self.pending_jobs.pop(0)
                    job.status = RenderStatus.RENDERING.value
                    job.assigned_slave = key
                    job.start_time = time.time()
                    self.active_jobs[key] = job
                    self.slaves[key].status = "rendering"
                    self.slaves[key].current_job_id = job.id

                    if self.on_job_assigned:
                        self.on_job_assigned(job, self.slaves[key])
                    if self.on_output:
                        self.on_output(f"Job {job.id} assigned to {self.slaves[key].hostname}")

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
                            self.on_output(f"Job {job_id} completed on {self.slaves.get(key, SlaveInfo('?','?',0)).hostname}")
                    else:
                        job.status = RenderStatus.FAILED.value
                        job.error_message = error
                        if key in self.slaves:
                            self.slaves[key].jobs_failed += 1
                        if self.on_job_failed:
                            self.on_job_failed(job, self.slaves.get(key))
                        if self.on_output:
                            self.on_output(f"Job {job_id} FAILED on {self.slaves.get(key, SlaveInfo('?','?',0)).hostname}: {error}")

                if key in self.slaves:
                    self.slaves[key].status = "idle"
                    self.slaves[key].current_job_id = ""

            return jsonify({"status": "ok"})

        @app.route("/api/status", methods=["GET"])
        def status():
            with self._lock:
                return jsonify({
                    "slaves": {k: v.to_dict() for k, v in self.slaves.items()},
                    "pending_jobs": len(self.pending_jobs),
                    "active_jobs": len(self.active_jobs),
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
            return jsonify({"pending": jobs, "active": active})

    def add_job(self, job: RenderJob):
        """Add a job to the distribution queue."""
        with self._lock:
            job.status = RenderStatus.PENDING.value
            self.pending_jobs.append(job)
        if self.on_output:
            self.on_output(f"Job added to farm queue: {job.project_name}")

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
            with self._lock:
                for key, slave in list(self.slaves.items()):
                    if not slave.is_alive and slave.status != "offline":
                        slave.status = "offline"
                        if self.on_slave_disconnected:
                            self.on_slave_disconnected(slave)
                        if self.on_output:
                            self.on_output(f"Slave disconnected: {slave.hostname}")
                        # Return any active jobs back to queue
                        if key in self.active_jobs:
                            job = self.active_jobs.pop(key)
                            job.status = RenderStatus.PENDING.value
                            job.assigned_slave = ""
                            self.pending_jobs.insert(0, job)
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
