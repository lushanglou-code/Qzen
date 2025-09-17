# -*- coding: utf-8 -*-
"""
后台工作线程模块。

定义了 `Worker` 类 (QThread的子类)，这是在Qt应用中执行后台任务的标准实践。

在图形用户界面（GUI）应用中，所有UI更新都必须在主线程中完成。如果
在主线程中执行耗时操作（如文件扫描、数据库查询、复杂计算），UI将
会冻结，无法响应用户输入。`Worker` 类的作用就是将这些耗时操作转移
到一个独立的后台线程中执行，并通过Qt的信号/槽机制将结果或错误安全
地传递回主UI线程，从而保持界面的流畅响应。
"""

from PyQt6.QtCore import QThread, pyqtSignal
from typing import Callable, Any
import logging

class Worker(QThread):
    """
    一个通用的、可重用的、可取消的后台工作线程。

    此类被设计为执行任何给定的函数，并在完成后通过信号发射其返回值或
    发生的任何异常。它还包含一个协作式的取消机制。

    Attributes:
        result_ready (pyqtSignal): 任务成功完成时发射的信号。
        error_occurred (pyqtSignal): 任务执行过程中发生异常时发射的信号。
        cancelled (pyqtSignal): 任务被用户取消时发射的信号。
    """
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(object)
    cancelled = pyqtSignal() # 新增：任务取消信号

    def __init__(self, func: Callable[..., Any], *args, **kwargs):
        """
        初始化工作线程。

        Args:
            func: 需要在后台线程中执行的目标函数。
            *args: 传递给目标函数的位置参数。
            **kwargs: 传递给目标函数的关键字参数。
        """
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._is_cancelled = False # 新增：取消标志

    def run(self):
        """
        线程的执行入口点。

        此方法会将 `self.is_cancelled` 方法作为 `is_cancelled_callback` 
        关键字参数传递给目标函数，允许业务逻辑层检查取消状态。
        """
        # 注入取消检查回调函数
        self._kwargs['is_cancelled_callback'] = self.is_cancelled
        try:
            result = self._func(*self._args, **self._kwargs)
            # 任务正常完成，但仍需检查是否在最后一刻被取消
            if self._is_cancelled:
                self.cancelled.emit()
            else:
                self.result_ready.emit(result)
        except Exception as e:
            # 如果是在取消过程中发生的异常，我们当作取消处理
            if self._is_cancelled:
                self.cancelled.emit()
            else:
                # 否则，是真正的错误
                self.error_occurred.emit(e)

    def cancel(self):
        """
        请求取消任务。

        这是一个“协作式”取消。它只是设置一个标志位。
        后台运行的函数逻辑需要主动、频繁地检查这个状态，并自行决定
        何时安全地中断其操作。
        """
        logging.info("接收到任务取消请求...")
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        """
        检查任务是否已被请求取消。

        Returns:
            如果任务已被请求取消，则返回 True，否则返回 False。
        """
        return self._is_cancelled
