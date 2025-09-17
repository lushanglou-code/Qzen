# -*- coding: utf-8 -*-
"""
配置对话框模块。

定义了 `ConfigDialog` 类，这是一个用于让用户输入和修改数据库
连接参数的模态对话框。
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
    """
    数据库连接配置对话框。

    此对话框提供了一个表单，让用户可以输入数据库的主机、端口、
    用户名和密码。它使用 `QSettings` 来自动加载和保存这些配置，
    从而实现持久化，方便用户下次使用。

    Attributes:
        host_input (QLineEdit): 用于输入主机地址的文本框。
        port_input (QLineEdit): 用于输入端口号的文本框。
        user_input (QLineEdit): 用于输入用户名的文本框。
        password_input (QLineEdit): 用于输入密码的文本框。
    """
    def __init__(self, parent=None):
        """
        初始化配置对话框。

        Args:
            parent: 父窗口部件，默认为 None。
        """
        super().__init__(parent)

        # --- 控件定义 ---
        self.host_input = QLineEdit()
        self.port_input = QLineEdit()
        self.user_input = QLineEdit()
        self.password_input = QLineEdit()
        # 将密码输入框设置为密码模式，输入的字符会显示为掩码
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        # --- 布局设置 ---
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.addRow(QLabel("主机地址:"), self.host_input)
        form_layout.addRow(QLabel("端   口:"), self.port_input)
        form_layout.addRow(QLabel("用 户 名:"), self.user_input)
        form_layout.addRow(QLabel("密   码:"), self.password_input)
        layout.addLayout(form_layout)

        # --- 标准按钮（OK, Cancel）设置 ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        # 将 'Ok' 按钮的 accepted 信号连接到此对话框的 accept 槽
        button_box.accepted.connect(self.accept)
        # 将 'Cancel' 按钮的 rejected 信号连接到此对话框的 reject 槽
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setWindowTitle("数据库配置")
        # 对话框启动时，自动加载上一次的设置
        self.load_settings()

    def load_settings(self) -> None:
        """
        从 `QSettings` 加载已保存的数据库配置并填充到输入框中。

        `QSettings` 是 Qt 提供的用于持久化存储应用配置的标准方式，
        它会自动处理在不同操作系统下的存储位置（如Windows注册表或INI文件）。
        """
        # 使用公司和应用名称来创建唯一的设置作用域
        settings = QSettings("Qzen", "config")
        self.host_input.setText(settings.value("db/host", "127.0.0.1"))
        self.port_input.setText(settings.value("db/port", "5236"))
        self.user_input.setText(settings.value("db/user", "GIMI"))
        self.password_input.setText(settings.value("db/password", "DM8DM8DM8"))

    def save_settings(self) -> None:
        """
        将当前输入框中的内容保存到 `QSettings` 中。
        """
        settings = QSettings("Qzen", "config")
        settings.setValue("db/host", self.host_input.text())
        settings.setValue("db/port", self.port_input.text())
        settings.setValue("db/user", self.user_input.text())
        settings.setValue("db/password", self.password_input.text())

    def get_db_url(self) -> str:
        """
        根据用户在对话框中输入的内容，构建一个 SQLAlchemy 连接 URL。

        Returns:
            一个格式化好的、可用于 `create_engine` 的数据库连接字符串。
        """
        # 根据 SQLAlchemy-DM 的官方文档，DM8 的方言名称是 'dm+dmPython'
        return (
            f"dm+dmPython://{self.user_input.text()}:{self.password_input.text()}"
            f"@{self.host_input.text()}:{self.port_input.text()}"
        )

    def accept(self) -> None:
        """
        重写 `QDialog` 的 `accept` 方法。在对话框被接受（用户点击OK）时，
        首先调用 `save_settings` 保存当前配置，然后才调用父类的 `accept`
        方法来关闭对话框并返回 `QDialog.DialogCode.Accepted`。
        """
        self.save_settings()
        super().accept()
