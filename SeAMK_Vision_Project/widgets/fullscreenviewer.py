from PySide6.QtWidgets import QDialog, QVBoxLayout, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QPainter
import numpy as np

class FullscreenViewer(QDialog):
    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        # Frameless window for a true fullscreen experience
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        # CONFIGURATION FOR SMOOTH PANNING (Like MVS)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag) # Left-click to Pan
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setInteractive(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.showFullScreen()

    def update_image(self, img_data):
        # 1. TYPE CHECK TO PREVENT SHAPE ERRORS
        if not isinstance(img_data, np.ndarray):
            return

        h, w = img_data.shape[:2]
        ch = img_data.shape[2] if len(img_data.shape) == 3 else 1
        
        # Convert to QImage
        fmt = QImage.Format_RGB888 if ch == 3 else QImage.Format_Grayscale8
        qt_img = QImage(img_data.data, w, h, ch * w, fmt)
        pixmap = QPixmap.fromImage(qt_img)
        
        if self.pixmap_item.pixmap().isNull():
            self.pixmap_item.setPixmap(pixmap)
            # Create a margin to allow comfortable panning
            margin = 500 
            self.scene.setSceneRect(-margin, -margin, w + margin*2, h + margin*2)
            self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        else:
            self.pixmap_item.setPixmap(pixmap)

    def wheelEvent(self, event):
        # ZOOM LOGIC: Scale up if wheeling forward, down if wheeling backward
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.view.scale(factor, factor)

    def keyPressEvent(self, event):
        # Press ESC to close viewer
        if event.key() == Qt.Key_Escape: 
            self.accept()