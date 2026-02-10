"""Capture screenshots of all 4 GUI tabs for documentation."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from src.gui.main_window import MainWindow
from src.gui.styles import DARK_THEME
from src.config import AppConfig
from src.moho_renderer import RenderJob, RenderStatus

SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Sample project files for demo
SAMPLE_PROJECTS = [
    r"d:\Apps\MohoRenderFarm\MohoProjects\056.4\056.4-Infinito-ESC01-v15.moho",
    r"d:\Apps\MohoRenderFarm\MohoProjects\076.2\076.2-Descuento-v35.moho",
    r"d:\Apps\MohoRenderFarm\MohoProjects\259.5\259.5-Primavera-V08-Color.moho",
    r"d:\Apps\MohoRenderFarm\MohoProjects\317.3\317.3-SerGrande-v02.moho",
    r"d:\Apps\MohoRenderFarm\MohoProjects\439.2\439.2-Puaj-v09.moho",
]


def populate_queue(window):
    """Add sample jobs with varied statuses for a realistic screenshot."""
    # Completed job
    job1 = RenderJob(
        project_file=SAMPLE_PROJECTS[0],
        format="MP4", options="MP4 (MPEG4-AAC)",
        output_path=r"D:\Renders\056.4-Infinito-ESC01-v15.mp4",
        status=RenderStatus.COMPLETED.value,
        progress=100.0, start_time=1000, end_time=1045,
        multithread=True, shapefx=True, layerfx=True, aa=True,
    )
    window.queue.jobs.append(job1)

    # Completed job
    job2 = RenderJob(
        project_file=SAMPLE_PROJECTS[1],
        format="MP4", options="MP4 (MPEG4-AAC)",
        output_path=r"D:\Renders\076.2-Descuento-v35.mp4",
        status=RenderStatus.COMPLETED.value,
        progress=100.0, start_time=1050, end_time=1112,
        multithread=True, shapefx=True, layerfx=True, aa=True,
    )
    window.queue.jobs.append(job2)

    # Rendering job
    job3 = RenderJob(
        project_file=SAMPLE_PROJECTS[2],
        format="MP4", options="MP4 (H.265-AAC)",
        output_path=r"D:\Renders\259.5-Primavera-V08-Color.mp4",
        status=RenderStatus.RENDERING.value,
        progress=67.0, start_time=1120, end_time=None,
        multithread=True, shapefx=True, layerfx=True, aa=True,
    )
    window.queue.jobs.append(job3)

    # Pending jobs
    job4 = RenderJob(
        project_file=SAMPLE_PROJECTS[3],
        format="PNG", options="",
        output_path=r"D:\Renders\317.3-SerGrande-v02.png",
        status=RenderStatus.PENDING.value,
        multithread=True, shapefx=True, layerfx=True, aa=True,
    )
    window.queue.jobs.append(job4)

    job5 = RenderJob(
        project_file=SAMPLE_PROJECTS[4],
        format="MP4", options="MP4 (MPEG4-AAC)",
        output_path=r"D:\Renders\439.2-Puaj-v09.mp4",
        status=RenderStatus.PENDING.value,
        multithread=True, shapefx=True, layerfx=True, aa=True,
    )
    window.queue.jobs.append(job5)

    # Refresh the table
    window._refresh_queue_table()

    # Add some log entries
    window._append_log("Moho Render Farm v1.0.0 started")
    window._append_log("Added 5 projects to queue")
    window._append_log("[a1b2c3d4] Starting render: 056.4-Infinito-ESC01-v15")
    window._append_log("[a1b2c3d4] Command: Moho.exe -r 056.4-Infinito-ESC01-v15.moho -f MP4 -options \"MP4 (MPEG4-AAC)\" -v")
    window._append_log("[a1b2c3d4] Render completed successfully (45s)")
    window._append_log("[e5f6g7h8] Starting render: 076.2-Descuento-v35")
    window._append_log("[e5f6g7h8] Render completed successfully (62s)")
    window._append_log("[i9j0k1l2] Starting render: 259.5-Primavera-V08-Color")
    window._append_log("[i9j0k1l2] Frame 161 (161/240)  2.34 secs/frame  185.06 secs remaining")


def populate_farm(window):
    """Add fake slave data for the farm tab screenshot."""
    from src.network.master import SlaveInfo
    import time

    # Simulate connected slaves
    slaves = {
        "192.168.1.10:5581": SlaveInfo("RENDER-PC-01", "192.168.1.10", 5581),
        "192.168.1.11:5581": SlaveInfo("RENDER-PC-02", "192.168.1.11", 5581),
        "192.168.1.12:5581": SlaveInfo("RENDER-PC-03", "192.168.1.12", 5581),
    }
    slaves["192.168.1.10:5581"].status = "rendering"
    slaves["192.168.1.10:5581"].current_job_id = "a1b2c3d4"
    slaves["192.168.1.10:5581"].jobs_completed = 3
    slaves["192.168.1.10:5581"].last_heartbeat = time.time()

    slaves["192.168.1.11:5581"].status = "idle"
    slaves["192.168.1.11:5581"].jobs_completed = 5
    slaves["192.168.1.11:5581"].jobs_failed = 1
    slaves["192.168.1.11:5581"].last_heartbeat = time.time()

    slaves["192.168.1.12:5581"].status = "rendering"
    slaves["192.168.1.12:5581"].current_job_id = "e5f6g7h8"
    slaves["192.168.1.12:5581"].jobs_completed = 2
    slaves["192.168.1.12:5581"].last_heartbeat = time.time()

    # Fill the slaves table
    window.slaves_table.setRowCount(len(slaves))
    from PyQt6.QtWidgets import QTableWidgetItem
    for row, (key, slave) in enumerate(slaves.items()):
        window.slaves_table.setItem(row, 0, QTableWidgetItem(slave.hostname))
        window.slaves_table.setItem(row, 1, QTableWidgetItem(key))
        window.slaves_table.setItem(row, 2, QTableWidgetItem(slave.status))
        window.slaves_table.setItem(row, 3, QTableWidgetItem(slave.current_job_id))
        window.slaves_table.setItem(row, 4, QTableWidgetItem(str(slave.jobs_completed)))
        window.slaves_table.setItem(row, 5, QTableWidgetItem(str(slave.jobs_failed)))

    # Set farm status label
    window.lbl_farm_status.setText("Master running on 192.168.1.5:5580")
    window.lbl_farm_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
    window.btn_start_master.setEnabled(False)
    window.btn_stop_master.setEnabled(True)
    window.btn_start_slave.setEnabled(False)


def take_screenshots(window):
    """Take a screenshot of each tab."""
    tab_names = [
        "01_render_queue",
        "02_render_settings",
        "03_render_farm",
        "04_app_settings",
    ]

    for i, name in enumerate(tab_names):
        window.tabs.setCurrentIndex(i)
        QApplication.processEvents()

        pixmap = window.grab()
        filepath = os.path.join(SCREENSHOT_DIR, f"{name}.png")
        pixmap.save(filepath, "PNG")
        print(f"Saved: {filepath}")

    print(f"\nAll {len(tab_names)} screenshots saved to {SCREENSHOT_DIR}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Moho Render Farm")
    app.setStyleSheet(DARK_THEME)

    config = AppConfig()
    window = MainWindow(config)
    window.resize(1300, 850)
    window.show()

    # Populate with demo data
    populate_queue(window)
    populate_farm(window)

    # Schedule screenshot capture after window is fully rendered
    QTimer.singleShot(500, lambda: take_screenshots(window))
    QTimer.singleShot(1500, app.quit)

    app.exec()


if __name__ == "__main__":
    main()
