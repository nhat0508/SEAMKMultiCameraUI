from PySide6.QtWidgets import QDialog, QVBoxLayout, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget

class FullscreenViewer(QDialog):
    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        
        # --- CẤU HÌNH TỐI ƯU CHO 12MP ---
        # 1. Sử dụng OpenGL để vẽ ảnh bằng GPU
        self.view.setViewport(QOpenGLWidget()) 
        
        # 2. Tối ưu hóa bộ đệm vẽ
        self.view.setCacheMode(QGraphicsView.CacheBackground)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # 3. Giảm bớt độ mượt khi nắn ảnh trong lúc Pan để tăng tốc độ phản hồi
        self.view.setRenderHint(QPainter.Antialiasing, False)
        self.view.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.resize(1200, 900)

    def update_image(self, image_data):
        # Chỉ cập nhật nếu cửa sổ thực sự đang hiển thị để tránh phí CPU
        if not self.isVisible():
            return
        
        if self.view.viewport().isEnabled():
            try:
                if hasattr(image_data, 'shape'):
                    h, w, ch = image_data.shape
                    q_img = QImage(image_data.data, w, h, ch * w, QImage.Format_RGB888)
                    pixmap = QPixmap.fromImage(q_img)
                else:
                    pixmap = QPixmap.fromImage(image_data)

                self.pixmap_item.setPixmap(pixmap)
                
                # Chỉ fit view lần đầu tiên khi mở
                if not hasattr(self, '_initial_fit'):
                    self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
                    self._initial_fit = True
                    
            except Exception as e:
                print(f"Viewer Error: {e}")

    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.view.scale(factor, factor)

    def keyPressEvent(self, event):
        # F11 để chuyển đổi giữa Toàn màn hình và Cửa sổ
        if event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        # Esc để đóng cửa sổ rời này
        elif event.key() == Qt.Key_Escape:
            self.close()