# -*- coding: utf-8 -*-
"""
UI 模块：配置标签页 (v2.1 - 路径规范化修复)。

此版本修复了在配置页面上显示和处理路径时，未使用平台原生路径分隔符的问题。
现在，所有设置路径的方法 (`set_path_text`, `set_all_configs`) 都会使用
`os.path.normpath()` 来确保显示的路径符合当前操作系统的标准 (e.g., 'E:\\folder')，
从 UI 源头保证了路径格式的一致性。
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QGridLayout, QLabel, QLineEdit, QPushButton, QSpinBox, 
    QPlainTextEdit, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal, Qt

class SetupTab(QWidget):
    """
    封装了“配置”标签页的所有 UI 控件和布局。

    通过信号-槽机制与主窗口通信，实现 UI 与业务逻辑的解耦。
    """
    # 定义当用户点击按钮时要发出的信号
    db_config_clicked = pyqtSignal()
    select_source_dir_clicked = pyqtSignal()
    select_intermediate_dir_clicked = pyqtSignal()
    select_target_dir_clicked = pyqtSignal()
    save_stopwords_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """创建并布局所有 UI 控件。"""
        layout = QGridLayout(self)

        # --- 数据库与路径配置 ---
        self.db_config_button = QPushButton("第一步：配置数据库")
        layout.addWidget(self.db_config_button, 0, 0, 1, 3)

        layout.addWidget(QLabel("第二步：源文件夹:"), 1, 0)
        self.source_dir_input = QLineEdit()
        self.source_dir_button = QPushButton("选择...")
        layout.addWidget(self.source_dir_input, 1, 1)
        layout.addWidget(self.source_dir_button, 1, 2)

        layout.addWidget(QLabel("第三步：中间文件夹 (核心工作目录):"), 2, 0)
        self.intermediate_dir_input = QLineEdit()
        self.intermediate_dir_button = QPushButton("选择...")
        layout.addWidget(self.intermediate_dir_input, 2, 1)
        layout.addWidget(self.intermediate_dir_button, 2, 2)

        layout.addWidget(QLabel("第四步：目标文件夹 (用于导出):"), 3, 0)
        self.target_dir_input = QLineEdit()
        self.target_dir_button = QPushButton("选择...")
        layout.addWidget(self.target_dir_input, 3, 1)
        layout.addWidget(self.target_dir_button, 3, 2)
        
        # --- 高级参数配置 ---
        layout.addWidget(QLabel("--- 高级参数配置 ---"), 4, 0, 1, 3)
        max_features_label = QLabel("TF-IDF 最大特征数 (?):")
        max_features_label.setToolTip("控制文本分析的词汇量。默认5000。")
        self.max_features_spinbox = QSpinBox()
        self.max_features_spinbox.setRange(1000, 50000)
        self.max_features_spinbox.setSingleStep(1000)
        layout.addWidget(max_features_label, 5, 0)
        layout.addWidget(self.max_features_spinbox, 5, 1)

        # --- 自定义停用词 ---
        stopwords_label = QLabel("自定义停用词 (?):")
        stopwords_label.setToolTip("在此输入希望在分析中忽略的词语，每行一个。")
        self.custom_stopwords_input = QPlainTextEdit()
        layout.addWidget(stopwords_label, 7, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.custom_stopwords_input, 7, 1, 1, 2)

        self.edit_stopwords_button = QPushButton("编辑")
        self.save_stopwords_button = QPushButton("保存并应用")

        stopwords_button_layout = QHBoxLayout()
        stopwords_button_layout.addStretch()
        stopwords_button_layout.addWidget(self.edit_stopwords_button)
        stopwords_button_layout.addWidget(self.save_stopwords_button)

        layout.addLayout(stopwords_button_layout, 8, 1, 1, 2)
        
        self.custom_stopwords_input.setReadOnly(True)
        self.save_stopwords_button.hide()

        layout.setRowStretch(9, 1) # 确保控件不会过度拉伸

    def _connect_signals(self):
        """将 UI 控件的事件连接到要发出的信号。"""
        self.db_config_button.clicked.connect(self.db_config_clicked.emit)
        self.source_dir_button.clicked.connect(self.select_source_dir_clicked.emit)
        self.intermediate_dir_button.clicked.connect(self.select_intermediate_dir_clicked.emit)
        self.target_dir_button.clicked.connect(self.select_target_dir_clicked.emit)
        
        self.edit_stopwords_button.clicked.connect(self._enter_edit_mode)
        self.save_stopwords_button.clicked.connect(self._on_save_stopwords)

    def _enter_edit_mode(self):
        """切换到停用词编辑模式。"""
        self.custom_stopwords_input.setReadOnly(False)
        self.edit_stopwords_button.hide()
        self.save_stopwords_button.show()

    def _leave_edit_mode(self):
        """退出编辑模式。"""
        self.custom_stopwords_input.setReadOnly(True)
        self.save_stopwords_button.hide()
        self.edit_stopwords_button.show()

    def _on_save_stopwords(self):
        """当保存按钮被点击时，发出信号并退出编辑模式。"""
        self.save_stopwords_clicked.emit(self.custom_stopwords_input.toPlainText())
        self._leave_edit_mode()

    # --- 公共接口 --- 

    def get_all_configs(self) -> dict:
        """获取此标签页上的所有配置项。"""
        return {
            "source_dir": self.source_dir_input.text(),
            "intermediate_dir": self.intermediate_dir_input.text(),
            "target_dir": self.target_dir_input.text(),
            "max_features": self.max_features_spinbox.value(),
            "custom_stopwords": self.custom_stopwords_input.toPlainText()
        }

    def set_all_configs(self, config: dict):
        """根据提供的字典，设置此标签页上的所有配置项，并确保路径为原生格式。"""
        source_dir = config.get("source_dir", "")
        self.source_dir_input.setText(os.path.normpath(source_dir) if source_dir else "")

        intermediate_dir = config.get("intermediate_dir", "")
        self.intermediate_dir_input.setText(os.path.normpath(intermediate_dir) if intermediate_dir else "")

        target_dir = config.get("target_dir", "")
        self.target_dir_input.setText(os.path.normpath(target_dir) if target_dir else "")

        self.max_features_spinbox.setValue(config.get("max_features", 5000))
        self.custom_stopwords_input.setPlainText(config.get("custom_stopwords", ""))

    def set_path_text(self, line_edit_name: str, path: str):
        """设置指定输入框的文本，并确保使用原生路径分隔符。"""
        if hasattr(self, line_edit_name):
            native_path = os.path.normpath(path) if path else ""
            getattr(self, line_edit_name).setText(native_path)
