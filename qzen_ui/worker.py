# -*- coding: utf-8 -*-
"""
后台工作线程模块。

定义了 Worker 类 (QThread的子类)，用于在后台执行所有耗时操作，
并通过信号(signal)将进度和结果安全地传递回主UI线程。
"""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import Callable, Any


class Worker(QThread):
    """执行耗时任务的后台线程。"""
    # 定义信号：
    # result_ready 信号在任务完成时发射，携带任务的返回值
    # error_occurred 信号在任务发生异常时发射，携带异常对象
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(object)

    def __init__(self, func: Callable[..., Any], *args, **kwargs):
        """
        初始化工作线程。

        Args:
            func: 需要在后台执行的函数。
            *args: func 的位置参数。
            **kwargs: func 的关键字参数。
        """
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        """线程执行的入口点。"""
        try:
            result = self._func(*self._args, **self._kwargs)
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(e)