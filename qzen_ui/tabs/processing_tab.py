# -*- coding: utf-8 -*-
"""
UI 模块：批量处理标签页 (v2.0)

定义了应用程序的第二个标签页，负责启动数据摄取流程。
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel
from PyQt6.QtCore import pyqtSignal

class ProcessingTab(QWidget):
    """
    封装了“批量处理”标签页的所有 UI 控件和布局。

    v2.0 中，此标签页的功能被简化为一个统一的“数据摄取”入口。
    """
    # 定义当用户点击按钮时要发出的信号
    start_ingestion_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """创建并布局所有 UI 控件。"""
        layout = QVBoxLayout(self)
        
        # v2.0 的核心入口按钮
        self.ingestion_button = QPushButton("开始数据摄取 (去重、预处理、向量化)")
        self.ingestion_button.setToolTip(
            "点击此按钮将启动一个完整的后台任务，该任务会：\n"
            "1. 清空并重建数据库。\n"
            "2. 清空并准备中间文件夹。\n"
            "3. 扫描源文件夹，去重后将唯一文件复制到中间文件夹。\n"
            "4. 对所有新文件进行文本提取和特征向量化。\n"
            "5. 将所有结果存入数据库。"
        )
        layout.addWidget(self.ingestion_button)
        
        # 用于显示日志或结果的区域
        layout.addWidget(QLabel("处理日志与结果:"))
        self.results_display = QTextEdit()
        self.results_display.setReadOnly(True)
        layout.addWidget(self.results_display)

    def _connect_signals(self):
        """将 UI 控件的事件连接到要发出的信号。"""
        self.ingestion_button.clicked.connect(self.start_ingestion_clicked.emit)

    # --- 公共接口 ---

    def set_button_enabled(self, enabled: bool):
        """设置按钮的可用状态。"""
        self.ingestion_button.setEnabled(enabled)

    def clear_results(self):
        """清空结果显示区域。"""
        self.results_display.clear()

    def append_result(self, text: str):
        """向结果显示区域追加文本。"""
        self.results_display.append(text)
