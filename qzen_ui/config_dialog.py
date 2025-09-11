# -*- coding: utf-8 -*-
"""
配置对话框模块。

定义了 ConfigDialog 类，用于让用户设置数据库连接、文件夹路径等参数。
"""

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QLabel,
)


class ConfigDialog(QDialog):
    """配置对话框窗口。"""
    def __init__(self, parent=None):
        """初始化配置对话框。"""
        super().__init__(parent)

        # --- 控件定义 ---
        self.host_input = QLineEdit()
        self.port_input = QLineEdit()
        self.user_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password) # 密码掩码

        # --- 布局设置 ---
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.addRow(QLabel("主机地址:"), self.host_input)
        form_layout.addRow(QLabel("端   口:"), self.port_input)
        form_layout.addRow(QLabel("用 户 名:"), self.user_input)
        form_layout.addRow(QLabel("密   码:"), self.password_input)
        layout.addLayout(form_layout)

        # --- 按钮设置 ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept) # 连接 'Ok' 按钮到 accept 槽
        button_box.rejected.connect(self.reject) # 连接 'Cancel' 按钮到 reject 槽
        layout.addWidget(button_box)

        self.setWindowTitle("数据库配置")
        self.load_settings()

    def load_settings(self) -> None:
        """从 QSettings 加载配置并填充到输入框。"""
        settings = QSettings("Qzen", "config")
        self.host_input.setText(settings.value("db/host", "127.0.0.1"))
        self.port_input.setText(settings.value("db/port", "5236"))
        self.user_input.setText(settings.value("db/user", "GIMI"))
        self.password_input.setText(settings.value("db/password", "DM8DM8DM8"))

    def save_settings(self) -> None:
        """将输入框中的内容保存到 QSettings。"""
        settings = QSettings("Qzen", "config")
        settings.setValue("db/host", self.host_input.text())
        settings.setValue("db/port", self.port_input.text())
        settings.setValue("db/user", self.user_input.text())
        settings.setValue("db/password", self.password_input.text())

    def get_db_url(self) -> str:
        """根据用户输入构建 SQLAlchemy 连接 URL。"""
        # 根据官方文档，方言名称大小写敏感，应为 'dm+dmPython'
        return (
            f"dm+dmPython://{self.user_input.text()}:{self.password_input.text()}"
            f"@{self.host_input.text()}:{self.port_input.text()}"
        )

    def accept(self) -> None:
        """重写 accept 方法，在对话框关闭前保存设置。"""
        self.save_settings()
        super().accept()