"""
Moho Render Farm - Main Entry Point
Created by Damián Turkieh

A comprehensive render farm and batch rendering tool for Moho Animation v14.
Supports individual and queue-based rendering, master/slave
render farm, and full CLI automation.
"""
import sys
import os
import socket
import json

# Add project root and vendored dependencies to path
_app_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_app_root, "lib"))
sys.path.insert(0, _app_root)

from src.config import AppConfig

IPC_PORT = 51780
IPC_HOST = '127.0.0.1'


def _try_send_to_running(files):
    """Try to send files to an already running instance. Returns True if successful."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((IPC_HOST, IPC_PORT))
        data = json.dumps({"files": [os.path.abspath(f) for f in files]}).encode('utf-8')
        sock.sendall(data)
        sock.close()
        return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False


def run_gui(initial_files=None, add_to_queue_files=None):
    """Launch the GUI application."""
    # Single-instance: try sending files to already running instance
    if add_to_queue_files:
        if _try_send_to_running(add_to_queue_files):
            return  # Sent to running instance, exit

    from PyQt6.QtWidgets import QApplication
    from src.gui.main_window import MainWindow
    from src.gui.styles import DARK_THEME

    app = QApplication(sys.argv)
    app.setApplicationName("Moho Render Farm")
    app.setOrganizationName("Damián Turkieh")
    app.setStyleSheet(DARK_THEME)

    config = AppConfig()
    window = MainWindow(config, initial_files=initial_files,
                        add_to_queue_files=add_to_queue_files)
    window.show()
    sys.exit(app.exec())


def main():
    """Main entry point - handles CLI args or launches GUI."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="moho-render-farm",
        description="Moho Render Farm - Render farm and batch rendering tool for Moho Animation v14. By Damián Turkieh.",
    )
    parser.add_argument("--render", "-r", nargs="+", metavar="FILE",
                        help="Render one or more Moho project files immediately")
    parser.add_argument("--add-to-queue", nargs="+", metavar="FILE",
                        help="Add files to the render queue in GUI mode")
    parser.add_argument("--format", "-f", default=None,
                        help="Output format (JPEG, PNG, MP4, etc.)")
    parser.add_argument("--options", default=None,
                        help="Format preset/codec (e.g. 'MP4 (MPEG4-AAC)')")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file or folder")
    parser.add_argument("--start", type=int, default=None,
                        help="Start frame number")
    parser.add_argument("--end", type=int, default=None,
                        help="End frame number")
    parser.add_argument("--moho-path", default=None,
                        help="Path to Moho.exe")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Quiet mode (no output)")
    parser.add_argument("--log", default=None,
                        help="Log file path")
    parser.add_argument("--multithread", type=str, default=None,
                        choices=["yes", "no"], help="Multi-threaded rendering")
    parser.add_argument("--halfsize", type=str, default=None,
                        choices=["yes", "no"], help="Render at half size")
    parser.add_argument("--halffps", type=str, default=None,
                        choices=["yes", "no"], help="Render at half frame rate")
    parser.add_argument("--shapefx", type=str, default=None,
                        choices=["yes", "no"], help="Apply shape effects")
    parser.add_argument("--layerfx", type=str, default=None,
                        choices=["yes", "no"], help="Apply layer effects")
    parser.add_argument("--fewparticles", type=str, default=None,
                        choices=["yes", "no"], help="Reduced particles")
    parser.add_argument("--aa", type=str, default=None,
                        choices=["yes", "no"], help="Antialiased edges")
    parser.add_argument("--extrasmooth", type=str, default=None,
                        choices=["yes", "no"], help="Extra-smooth images")
    parser.add_argument("--premultiply", type=str, default=None,
                        choices=["yes", "no"], help="Premultiply alpha")
    parser.add_argument("--ntscsafe", type=str, default=None,
                        choices=["yes", "no"], help="NTSC safe colors")
    parser.add_argument("--layercomp", default=None,
                        help="Layer comp name (or AllComps/AllLayerComps)")
    parser.add_argument("--addlayercompsuffix", type=str, default=None,
                        choices=["yes", "no"], help="Add layer comp suffix")
    parser.add_argument("--createfolderforlayercomps", type=str, default=None,
                        choices=["yes", "no"], help="Create folder for layer comps")
    parser.add_argument("--addformatsuffix", type=str, default=None,
                        choices=["yes", "no"], help="Add format suffix")
    parser.add_argument("--quality", type=int, default=None,
                        choices=range(6), help="Quality 0-5 (QT only)")
    parser.add_argument("--depth", type=int, default=None,
                        help="Pixel depth (QT only, e.g. 24 or 32)")
    parser.add_argument("--queue-file", default=None,
                        help="Load and process a saved queue file")
    parser.add_argument("--save-queue", default=None,
                        help="Save the queue to a file after adding render files")
    parser.add_argument("--slave", action="store_true",
                        help="Start in slave mode (headless)")
    parser.add_argument("--master-host", default="localhost",
                        help="Master host address for slave mode")
    parser.add_argument("--port", type=int, default=5580,
                        help="Network port for master/slave")
    parser.add_argument("--register-context-menu", action="store_true",
                        help="Register Windows right-click context menu")
    parser.add_argument("--unregister-context-menu", action="store_true",
                        help="Remove Windows right-click context menu")
    parser.add_argument("--gui", action="store_true",
                        help="Force GUI mode")

    args = parser.parse_args()

    # Handle context menu registration
    if args.register_context_menu:
        from src.utils.context_menu import register_context_menu
        register_context_menu()
        return

    if args.unregister_context_menu:
        from src.utils.context_menu import unregister_context_menu
        unregister_context_menu()
        return

    # Handle slave mode
    if args.slave:
        _run_slave_mode(args)
        return

    # Handle CLI render mode
    if args.render:
        _run_cli_render(args)
        return

    # Handle queue file processing
    if args.queue_file and not args.gui:
        _run_queue_file(args)
        return

    # Default: launch GUI
    run_gui(
        add_to_queue_files=args.add_to_queue,
    )


def _yn_to_bool(val):
    """Convert 'yes'/'no' string to bool or None."""
    if val is None:
        return None
    return val == "yes"


def _run_cli_render(args):
    """Render files from the command line."""
    from src.moho_renderer import RenderJob, MohoRenderer, RenderStatus

    config = AppConfig()
    moho_path = args.moho_path or config.moho_path

    if not os.path.exists(moho_path):
        print(f"ERROR: Moho executable not found: {moho_path}")
        sys.exit(1)

    renderer = MohoRenderer(moho_path)
    failed = 0

    for filepath in args.render:
        if not os.path.exists(filepath):
            print(f"ERROR: File not found: {filepath}")
            failed += 1
            continue

        job = RenderJob()
        job.project_file = filepath
        if args.format:
            job.format = args.format
        if args.options:
            job.options = args.options
        if args.output:
            job.output_path = args.output
        job.start_frame = args.start
        job.end_frame = args.end
        job.verbose = args.verbose
        job.quiet = args.quiet
        if args.log:
            job.log_file = args.log
        job.multithread = _yn_to_bool(args.multithread)
        job.halfsize = _yn_to_bool(args.halfsize)
        job.halffps = _yn_to_bool(args.halffps)
        job.shapefx = _yn_to_bool(args.shapefx)
        job.layerfx = _yn_to_bool(args.layerfx)
        job.fewparticles = _yn_to_bool(args.fewparticles)
        job.aa = _yn_to_bool(args.aa)
        job.extrasmooth = _yn_to_bool(args.extrasmooth)
        job.premultiply = _yn_to_bool(args.premultiply)
        job.ntscsafe = _yn_to_bool(args.ntscsafe)
        if args.layercomp:
            job.layercomp = args.layercomp
        job.addlayercompsuffix = _yn_to_bool(args.addlayercompsuffix)
        job.createfolderforlayercomps = _yn_to_bool(args.createfolderforlayercomps)
        job.addformatsuffix = _yn_to_bool(args.addformatsuffix)
        job.quality = args.quality
        job.depth = args.depth

        print(f"Rendering: {filepath}")
        result = renderer.render(
            job,
            on_output=lambda msg: print(msg) if not args.quiet else None,
        )

        if result.status == RenderStatus.COMPLETED.value:
            print(f"Completed: {filepath} ({result.elapsed_str})")
        else:
            print(f"FAILED: {filepath} - {result.error_message}")
            failed += 1

    if failed:
        print(f"\n{failed} job(s) failed")
        sys.exit(1)
    else:
        print(f"\nAll {len(args.render)} job(s) completed successfully")


def _run_queue_file(args):
    """Process a saved queue file from CLI."""
    from src.render_queue import RenderQueue

    config = AppConfig()
    moho_path = args.moho_path or config.moho_path

    if not os.path.exists(moho_path):
        print(f"ERROR: Moho executable not found: {moho_path}")
        sys.exit(1)

    queue = RenderQueue(moho_path)
    queue.on_output = lambda msg: print(msg) if not args.quiet else None
    queue.on_job_completed = lambda j: print(f"Completed: {j.project_name} ({j.elapsed_str})")
    queue.on_job_failed = lambda j: print(f"FAILED: {j.project_name} - {j.error_message}")
    queue.on_queue_completed = lambda: print("All queue jobs completed!")

    try:
        queue.load_queue(args.queue_file)
        print(f"Loaded {queue.total_jobs} jobs from {args.queue_file}")
    except Exception as e:
        print(f"ERROR: Failed to load queue: {e}")
        sys.exit(1)

    import time
    queue.start()
    while queue.is_running:
        time.sleep(1)

    failed = queue.failed_count
    if failed:
        sys.exit(1)


def _run_slave_mode(args):
    """Run in headless slave mode."""
    from src.network.slave import SlaveClient

    config = AppConfig()
    moho_path = args.moho_path or config.moho_path
    host = args.master_host
    port = args.port

    print(f"Starting slave mode, connecting to {host}:{port}")
    print(f"Moho path: {moho_path}")

    slave = SlaveClient(host, port, moho_path, slave_port=port + 1)
    slave.on_output = lambda msg: print(f"[SLAVE] {msg}")

    slave.start()

    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping slave...")
        slave.stop()


if __name__ == "__main__":
    main()
