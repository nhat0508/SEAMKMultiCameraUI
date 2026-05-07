import os
import sys
from widgets.utils.config import HIKROBOT_BIN, HIKROBOT_CTI

# Force UTF-8 encoding
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# Load DLLs to prevent C++ library loading errors
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(HIKROBOT_BIN)

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton
from PySide6.QtCore import Qt
from harvesters.core import Harvester
from camera_thread import CameraThread
from widgets.preview_window import PreviewWindow

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SEAMK Unified Camera System")
        self.resize(1200, 800)
        
        # USE A SINGLE HARVESTER INSTANCE
        self.h = Harvester()
        try:
            self.h.add_file(HIKROBOT_CTI)
            self.h.update()
            print(f"CTI loaded. Found: {len(self.h.device_info_list)} camera(s).")
        except Exception as e:
            print(f"Harvester system initialization error: {e}")

        self.threads = [] 
        self.previews = [] 
        self.acquirers = [] 
        self.show_selection_ui()

    def show_selection_ui(self):
        self.selection_widget = QWidget()
        layout = QVBoxLayout()
        self.checkboxes = []

        # Display all cameras found (e.g., Basler and Hikrobot)
        for info in self.h.device_info_list:
            cb = QCheckBox(f"[{info.vendor}] {info.model} ({info.id_})")
            layout.addWidget(cb)
            self.checkboxes.append((cb, info))

        ok_btn = QPushButton("Connect Selected Cameras")
        ok_btn.setFixedHeight(40)
        ok_btn.clicked.connect(self.start_streaming)
        layout.addWidget(ok_btn)
        
        self.selection_widget.setLayout(layout)
        self.setCentralWidget(self.selection_widget)

    def start_streaming(self):
        selected_info = [info for cb, info in self.checkboxes if cb.isChecked()]
        if not selected_info: return

        self.main_widget = QWidget()
        self.main_layout = QHBoxLayout()

        for index, info in enumerate(selected_info):
            print(f"Initializing: {info.model}")
            try:
                # Use the single Harvester instance to create connection
                ia = self.h.create({'id_': info.id_})
                self.acquirers.append(ia)
                
                is_main = (index == 0)
                preview = PreviewWindow(info, ia, is_main=is_main)
                thread = CameraThread(ia, info)
                preview.set_thread(thread) 
                
                # Connect image signal to the preview window
                thread.change_pixmap_signal.connect(preview.update_image, Qt.QueuedConnection)
                
                if is_main:
                    preview.sync_toggled_signal.connect(self.toggle_sync_mode)
                    preview.global_snapshot_signal.connect(self.take_global_snapshot)
                    preview.global_record_signal.connect(self.toggle_global_record)
                    preview.global_start_snap_signal.connect(self.start_global_snap)
                    preview.global_stop_snap_signal.connect(self.stop_global_snap)
                
                # Connect Focus Mode signal (Bandwidth management)
                preview.focus_mode_signal.connect(self.handle_focus_mode)
                
                self.main_layout.addWidget(preview)
                self.previews.append(preview)
                self.threads.append(thread)
                thread.start()

            except Exception as e:
                print(f"CAMERA INITIALIZATION ERROR {info.model}: {e}")

        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

    def handle_focus_mode(self, active_preview, is_focus):
        for p, t in zip(self.previews, self.threads):
            if p != active_preview: 
                if is_focus:
                    t.pause_camera() 
                    p.image_label.setStyleSheet("background-color: black; opacity: 0.5; border: 2px solid red;")
                else:
                    t.resume_camera()
                    p.image_label.setStyleSheet("background-color: black; border: 1px solid #333;")

    # --- Synchronized functions ---
    def toggle_sync_mode(self, is_synced):
        for i in range(1, len(self.previews)):
            self.previews[i].set_buttons_enabled(not is_synced)

    def take_global_snapshot(self):
        for p in self.previews: p.take_local_snapshot()

    def toggle_global_record(self, state):
        for p in self.previews: p.set_local_record(state)

    def start_global_snap(self, interval):
        for p in self.previews: p.start_local_snap(interval)

    def stop_global_snap(self):
        for p in self.previews: p.stop_local_snap()

    def closeEvent(self, event):
        # Stop all threads
        for t in self.threads: t._run_flag = False
        for t in self.threads: t.wait(1500)
        
        # Cleanup acquirers
        for ia in self.acquirers:
            try:
                if ia.remote_device: 
                    ia.remote_device.node_map.AcquisitionStop.execute()
                ia.destroy()
            except: pass
            
        self.acquirers.clear()
        self.threads.clear()
        
        try: self.h.reset()
        except: pass
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())