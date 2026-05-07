# SEAMK Unified Camera System

A centralized industrial camera management and control system supporting both Basler and Hikrobot camera series. The project provides Live View capabilities, lens calibration, synchronized photo/video capture, and transmission bandwidth optimization.

## Key Features

### 1. Multi-Camera Management
* **Auto-Discovery:** Automatically detects cameras within the LAN/GigE network via the GenICam protocol (Harvester).
* **Cross-Vendor Support:** Supports a combination of different camera brands (Basler, Hikrobot) within a single control interface.

### 2. Image Processing & Calibration
* **Camera Calibration:** Integrated tools to calculate camera matrices ($K$) and distortion coefficients ($dist$) using a Chessboard pattern.
* **Undistortion:** Applies real-time image undistortion using CPU-optimized remap algorithms.
* **Color Processing:** Automatic format conversion from Bayer (RG, BG, GB, GR) and YUV to BGR for display and storage.

### 3. Synchronized Control
* **Synchronized Mode:** Enables simultaneous Snapshot or Video Recording across all connected cameras with a single action from the Main camera.
* **Interval Capture:** Set up automated periodic snapshots for continuous monitoring.

### 4. Performance Optimization
* **Focus Mode:** Automatically pauses secondary camera streams when a specific camera is opened in Fullscreen to prioritize network bandwidth and processing resources.
* **Multithreading:** Each camera operates on its own `QThread`, ensuring the User Interface remains responsive.

## System Requirements
* **Python:** 3.10+
* **Libraries:** `opencv-python`, `PySide6`, `harvesters`, `numpy`, `matplotlib`.
* **Prerequisites:** MVS SDK (Hikrobot) or Pylon SDK (Basler) to provide the necessary `.cti` driver files.

## Setup and MVS Configuration
To ensure system stability and optimize data transmission, you must perform the following configuration steps in the Hikrobot MVS software:

1.  **Load Configuration:** Import the 3 provided `.mfa` files into the MVS software to set the default parameters for the cameras.
2.  **Bandwidth Configuration:**
    * Open the camera tools in MVS.
    * Adjust the bandwith as shown in the reference image `MVS_bandwith_setting.PNG`.
    * This step is crucial to prevent **Packet Loss** when running multiple high-resolution cameras simultaneously.

## Source Code Structure
* `main.py`: Entry point of the application; manages connections and the main UI.
* `camera_thread.py`: Handles raw data acquisition, color decoding, and image correction.
* `calibration_functions.py`: Library of mathematical functions for camera calibration.
* `preview_window.py`: Individual control widgets for each camera (Snapshot, Record, Calib).
* `settings_dialog.py`: Camera parameter configuration (Exposure, FPS, Binning, Storage).
* `calib_example.py`: Sample script to perform the calibration parameter extraction process.

## Single Camera Calibration Guide
1.  **Calibration:** Use `calib_example.py` with a set of chessboard images to export the `intrinsics_60gc_calibration.json` file.
2.  **Launch:** Run `python main.py`, select your cameras, and click "Connect Selected Cameras".
3.  **Undistortion:** Click "Load JSON" in the preview window, select the generated `.json` file, and check the "Undistort" box.

## Path Configuration Note
Edit the `config.py` file to point to the correct `.cti` driver path on your machine:

```python
import os
HIKROBOT_BIN = r'C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64'
HIKROBOT_CTI = os.path.join(HIKROBOT_BIN, 'MvProducerGEV.cti')
