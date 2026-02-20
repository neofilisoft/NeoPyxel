from PyQt5.QtCore import QMimeData, Qt
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QListWidget

class AssetListWidget(QListWidget):
    def startDrag(self, supported_actions):
        item = self.currentItem()
        if not item:
            return
        asset_path = item.data(Qt.UserRole)
        if not asset_path:
            return

        mime = QMimeData()
        mime.setText(asset_path)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.CopyAction)
