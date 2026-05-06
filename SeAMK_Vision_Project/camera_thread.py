import numpy as np
import cv2, os, time, json
from PySide6.QtCore import QThread, Signal
# Ensure the import path to your calibration_functions.py is correct
from calibration.calibration_functions import undistort_image, get_undistort_map, fast_undistort_image

class CameraThread(QThread):
    change_pixmap_signal = Signal(np.ndarray) 

    def __init__(self, ia, info):
        super().__init__()
        self.ia = ia
        self.info = info
        self._run_flag = True
        
        self._is_paused = False       
        self.emit_full_res = False    
        self.config = {}

        self.last_full_frame = None
        self.video_writer = None
        self.is_recording = False

        # Calibration Parameters
        self.calib_mtx = None
        self.calib_dist = None
        self.calib_newcameramtx = None
        self.is_calibrated = False
        self.enable_undistort = False 
        
        # Undistort Map Cache (CPU Optimization)
        self.mapx = None
        self.mapy = None

    def pause_camera(self):
        self._is_paused = True 

    def resume_camera(self):
        self._is_paused = False

    def set_full_res(self, state):
        self.emit_full_res = state

    def run(self):
        self.setPriority(QThread.LowPriority)
        nodemap = self.ia.remote_device.node_map
        time.sleep(0.5)
        
        vendor_name = str(self.info.vendor).lower()
        model_name = str(self.info.model).lower()
        fps_target = 5.0 

        # --- SAFE PARAMETER SETTER (Robust against cable disconnects) ---
        def safe_set(node_name, value):
            if node_name in dir(nodemap):
                try:
                    node = getattr(nodemap, node_name)
                    # Handle Enumeration nodes (like On/Off)
                    if hasattr(node, 'selectors') and isinstance(value, bool):
                        node.value = "On" if value else "Off"
                    else:
                        node.value = value
                except:
                    pass

        # 1. BASIC INITIALIZATION
        safe_set("ExposureAuto", "Off")
        safe_set("GainAuto", "Off")
        safe_set("BinningHorizontal", 1)
        safe_set("BinningVertical", 1)
        
        # Set FPS to 5.0
        safe_set("AcquisitionFrameRateEnable", True)
        safe_set("AcquisitionFrameRate", fps_target)
        safe_set("AcquisitionFrameRateAbs", fps_target)

        # 2. BANDWIDTH OPTIMIZATION
        # Prioritize DeviceLinkThroughputLimit (Equivalent to Bandwidth Adjust in MVS)
        if "hik" in vendor_name:
            safe_set("DeviceLinkThroughputLimit", 500000000) # 500 Mbps for Hik 12MP
            safe_set("GevSCPD", 7000)                        # Optimal Packet Delay for Hik
            safe_set("GevSCPSPacketSize", 8164)              # Jumbo Frame
            self.ia.num_buffers = 15                         # Large buffer for heavy images
        else:
            # Basler 1.9MP
            safe_set("DeviceLinkThroughputLimit", 100000000) # 100 Mbps for Basler
            safe_set("GevSCPD", 10000)                       # Optimal Packet Delay for Basler
            safe_set("GevSCPSPacketSize", 1500)
            self.ia.num_buffers = 5

        safe_set("GevHeartbeatTimeout", 5000)

        # 3. ACQUISITION AND IMAGE PROCESSING LOOP
        try:
            try:
                if not self.ia.is_acquiring(): 
                    self.ia.remote_device.node_map.BinningHorizontal.value = "X2"
                    self.ia.remote_device.node_map.BinningVertical.value = "X2"
            except:
                try:
                    self.ia.remote_device.node_map.BinningHorizontal.value = 2
                except Exception as e:
                    print(f"Cannot set Binning: {e}")
                    
            self.ia.start()
            while self._run_flag:
                try:
                    # FETCH: Get raw data and exit quickly to release Buffer
                    with self.ia.fetch(timeout=3.0) as buffer:
                        if self._is_paused:
                            continue 

                        payload = buffer.payload
                        component = payload.components[0]
                        w, h = component.width, component.height
                        data_format = component.data_format
                        raw_data = component.data.copy() # Copy to process outside the 'with' block
                        bytes_per_pixel = len(raw_data) // (w * h)

                except Exception as e:
                    print(f"⚠️ [Signal Lost] {self.info.model}: {type(e).__name__}")
                    time.sleep(0.05)
                    continue 

                # IMAGE PROCESSING (Outside 'with' block to prevent network congestion)
                try:
                    # Accurate color decoding for different Camera types
                    if "hik" in vendor_name and bytes_per_pixel == 1:
                        raw = raw_data.reshape(h, w)
                        if self.config.get('color_mode') == "Grayscale":
                            full_img = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
                        else:
                            full_img = cv2.cvtColor(raw, cv2.COLOR_BayerRG2RGB)
                    else:
                        if bytes_per_pixel == 3:
                            full_img = raw_data.reshape(h, w, 3)
                            if "RGB" in data_format: full_img = cv2.cvtColor(full_img, cv2.COLOR_RGB2BGR)
                        elif "YUV" in data_format or "yuv" in data_format.lower():
                            raw = raw_data.reshape(h, w, 2)
                            full_img = cv2.cvtColor(raw, cv2.COLOR_YUV2BGR_YUYV)
                        elif "Bayer" in data_format:
                            raw = raw_data.reshape(h, w)
                            if "BayerRG" in data_format: full_img = cv2.cvtColor(raw, cv2.COLOR_BayerRG2RGB)
                            elif "BayerBG" in data_format: full_img = cv2.cvtColor(raw, cv2.COLOR_BayerBG2RGB)
                            elif "BayerGB" in data_format: full_img = cv2.cvtColor(raw, cv2.COLOR_BayerGB2RGB)
                            else: full_img = cv2.cvtColor(raw, cv2.COLOR_BayerGR2RGB)
                        else:
                            raw = raw_data.reshape(h, w)
                            full_img = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)

                    self.last_full_frame = full_img 
                    
                    # Apply high-speed Calibration Undistort
                    if self.enable_undistort and self.is_calibrated:
                        if self.mapx is None or self.mapy is None:
                            # Initialize undistort maps once
                            self.mapx, self.mapy = get_undistort_map(w, h, self.calib_mtx, self.calib_dist, self.calib_newcameramtx)
                        full_img = fast_undistort_image(full_img, self.mapx, self.mapy)

                    # Convert color for UI display
                    if self.config.get('color_mode') == "Grayscale" and len(full_img.shape) == 3:
                        full_img = cv2.cvtColor(full_img, cv2.COLOR_BGR2GRAY)

                    # Write Video if Recording is enabled
                    if self.is_recording and self.video_writer:
                        rec_frame = full_img if len(full_img.shape) == 3 else cv2.cvtColor(full_img, cv2.COLOR_GRAY2BGR)
                        self.video_writer.write(rec_frame)
                        
                    # Prepare Preview image for UI
                    if self.emit_full_res:
                        preview_rgb = cv2.cvtColor(full_img, cv2.COLOR_BGR2RGB) if len(full_img.shape) == 3 else cv2.cvtColor(full_img, cv2.COLOR_GRAY2RGB)
                    else:
                        preview_small = cv2.resize(full_img, (400, 300), interpolation=cv2.INTER_NEAREST)
                        preview_rgb = cv2.cvtColor(preview_small, cv2.COLOR_BGR2RGB) if len(preview_small.shape) == 3 else cv2.cvtColor(preview_small, cv2.COLOR_GRAY2RGB)
                
                    self.change_pixmap_signal.emit(preview_rgb)
                    
                except Exception as e:
                    print(f"OpenCV Error ({self.info.model}): {e}")

        finally:
            self.stop_recording()
            try: self.ia.stop()
            except: pass

    # --- UTILITY FUNCTIONS ---
    def take_snapshot(self, folder, name):
        if self.last_full_frame is not None:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"{name}_{int(time.time()*1000)}.jpg")
            cv2.imwrite(path, self.last_full_frame)

    def start_recording(self, folder, name, fps):
        if self.last_full_frame is None: return
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{name}_{int(time.time())}.mp4")
        h, w = self.last_full_frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
        self.video_writer = cv2.VideoWriter(path, cv2.CAP_FFMPEG, fourcc, fps, (w, h), isColor=True)
        self.is_recording = True

    def stop_recording(self):
        self.is_recording = False
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

    def load_calibration_file(self, json_path):
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
                self.calib_mtx = np.array(data['camera_matrix'])
                self.calib_dist = np.array(data['dist_coeffs'])
                self.calib_newcameramtx = np.array(data.get('new_camera_matrix', data['camera_matrix']))
            self.is_calibrated = True
            self.mapx = None # Reset maps to recalculate based on new file
            self.mapy = None
            print(f"✅ Calibration file loaded for {self.info.model}")
            return True
        except Exception as e:
            print(f"❌ JSON Load Error: {e}")
            self.is_calibrated = False
            return False

    def toggle_undistort(self, state):
        self.enable_undistort = state
        
    def stop(self):
        self._run_flag = False
        self.wait(2000)