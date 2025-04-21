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
        self.setFixedSize(360, 250)

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

        # === Output directory selection (horizontal layout) ===
        path_layout = QtWidgets.QHBoxLayout()
        path_label = QtWidgets.QLabel("Output directory:")
        self.output_path_box = QtWidgets.QLineEdit(self.output_dir)
        self.output_path_box.setReadOnly(True)
        browse_btn = QtWidgets.QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self.choose_output_folder)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.output_path_box)
        path_layout.addWidget(browse_btn)

        # === Filename input ===
        self.filename_input = QtWidgets.QLineEdit()
        self.filename_input.setPlaceholderText("Enter base filename")

        # === Export button ===
        self.export_btn = QtWidgets.QPushButton("Export VAT")
        self.export_btn.clicked.connect(self.export_vat)

        # === Progress bar ===
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

        # === Reset button ===
        self.reset_btn = QtWidgets.QPushButton("Reset")
        self.reset_btn.clicked.connect(self.reset_ui)

        # === Layout assembly ===
        layout.addWidget(QtWidgets.QLabel("Select a skinned mesh :"))
        layout.addLayout(path_layout)
        layout.addWidget(QtWidgets.QLabel("Base filename:"))
        layout.addWidget(self.filename_input)
        layout.addWidget(self.export_btn)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.reset_btn)

        self.setCentralWidget(central_widget)

    def choose_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Folder", self.output_dir)
        if folder:
            self.output_dir = folder
            self.output_path_label.setText(f"Output directry:<br>{self.output_dir}")

    def export_vat(self):
        try:
            self.progress_bar.setValue(0)
            base_name = self.filename_input.text().strip()
            if not base_name:
                QtWidgets.QMessageBox.warning(self, "Missing Filename", "Please enter a base filename.")
                return
            def progress_callback(percent):
                self.progress_bar.setValue(percent)
            vat.make_dat_texture(output_dir=self.output_dir, base_filename=base_name, progress_fn=progress_callback)
            self.progress_bar.setValue(100)
            
            QtWidgets.QMessageBox.information(self, "Export Complete", "VAT export finished successfully.")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Failed", str(e))

    def choose_output_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Folder", self.output_dir)
        if folder:
            self.output_dir = folder
            self.output_path_box.setText(self.output_dir)
    
    
    def reset_ui(self):
        ### reset setting
        project_dir = cmds.workspace(q=True, rootDirectory=True)
        images_dir = cmds.workspace(fileRuleEntry="images")
        self.output_dir = os.path.join(project_dir, images_dir) if images_dir else os.path.join(project_dir, "images")

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        self.output_path_box.setText(self.output_dir)
        self.filename_input.clear()
        self.progress_bar.setValue(0)

def show_ui():
    global ui_instance
    try:
        ui_instance.close()
        ui_instance.deleteLater()
    except:
        pass
    ui_instance = VATExporterUI()
    ui_instance.show()