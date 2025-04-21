from . import VAT_Exporter as vat
import maya.cmds as cmds
from PySide6 import QtWidgets, QtCore
from maya.app.general.mayaMixin import MayaQWidgetBaseMixin
import os

class VATExporterUI(MayaQWidgetBaseMixin, QtWidgets.QMainWindow):
    def __init__(self):
        ### initial setting for window
        super(VATExporterUI, self).__init__()
        self.setWindowTitle("VAT Exporter")
        self.setFixedSize(300, 180)
        scene_path = cmds.file(q=True, sceneName=True)
        project_dir = cmds.workspace(q=True, rootDirectory=True)
        images_dir = cmds.workspace(fileRuleEntry="images")
        self.output_dir = os.path.join(project_dir, images_dir) if images_dir else os.path.join(project_dir, "images")
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        self.init_ui()

    def init_ui(self):
        ### make UI component
        central_widget = QtWidgets.QWidget() # set layout
        layout = QtWidgets.QVBoxLayout(central_widget) # Vertical layout

        self.output_path_label = QtWidgets.QLabel()
        self.output_path_label.setTextFormat(QtCore.Qt.RichText)
        self.output_path_label = QtWidgets.QLabel(f"Output directry:<br>{self.output_dir}")
        self.browse_btn = QtWidgets.QPushButton("Choose Output Folder")
        self.browse_btn.clicked.connect(self.choose_output_folder)

        self.export_btn = QtWidgets.QPushButton("Export VAT")
        self.export_btn.clicked.connect(self.export_vat)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

        layout.addWidget(QtWidgets.QLabel("Select a skinned mesh :"))
        layout.addWidget(self.output_path_label)
        layout.addWidget(self.browse_btn)
        layout.addWidget(self.export_btn)
        layout.addWidget(self.progress_bar)

        self.setCentralWidget(central_widget)

    def choose_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Folder", self.output_dir)
        if folder:
            self.output_dir = folder
            self.output_path_label.setText(f"Output directry:<br>{self.output_dir}")

    def export_vat(self):
        try:
            self.progress_bar.setValue(0)
            def progress_callback(percent):
                self.progress_bar.setValue(percent)
            vat.make_dat_texture(output_dir=self.output_dir, progress_fn=progress_callback)
            self.progress_bar.setValue(100)
            
            QtWidgets.QMessageBox.information(self, "Export Complete", "VAT export finished successfully.")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(e))

def show_ui():
    global ui_instance
    try:
        ui_instance.close()
        ui_instance.deleteLater()
    except:
        pass
    ui_instance = VATExporterUI()
    ui_instance.show()