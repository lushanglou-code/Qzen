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


class Worker(QThread):
    """
    一个通用的、可重用的后台工作线程。

    此类被设计为执行任何给定的函数，并在完成后通过信号发射其返回值或
    发生的任何异常。

    Attributes:
        result_ready (pyqtSignal): 任务成功完成时发射的信号。它携带一个
                                 `object` 类型的参数，即被执行函数的返回值。
        error_occurred (pyqtSignal): 任务执行过程中发生异常时发射的信号。
                                   它携带一个 `object` 类型的参数，即捕获到
                                   的异常对象。
    """
    # 定义信号：
    # result_ready 信号在任务成功完成时发射，携带任务的返回值。
    # object 类型意味着它可以携带任何Python对象。
    result_ready = pyqtSignal(object)
    # error_occurred 信号在任务发生异常时发射，携带异常对象。
    error_occurred = pyqtSignal(object)

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

    def run(self):
        """
        线程的执行入口点。

        当调用 `worker.start()` 时，Qt会创建一个新线程并执行此 `run` 方法。
        此方法的核心逻辑是调用传入的目标函数，并将其返回值或捕获到的
        异常通过对应的信号发射出去。
        """
        try:
            # 执行传入的耗时函数，并捕获其返回值
            result = self._func(*self._args, **self._kwargs)
            # 发射成功信号，将结果传递回主线程
            self.result_ready.emit(result)
        except Exception as e:
            # 如果函数执行过程中出现任何异常，则捕获它
            # 并发射错误信号，将异常对象传递回主线程
            self.error_occurred.emit(e)
