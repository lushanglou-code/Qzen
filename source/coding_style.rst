.. _coding-style:

##########################
编码规范与API设计指南
##########################

本指南为 Qzen 项目的所有代码贡献者提供了一套统一的编码风格和API设计原则，旨在提高代码的可读性、一致性和可维护性。

基本原则
==================

所有Python代码 **必须** 严格遵守 `PEP 8 -- Style Guide for Python Code <https://www.python.org/dev/peps/pep-0008/>`_。

命名约定
==================

* **模块 (Modules)**: 使用小写字母和下划线，例如 ``similarity_engine.py``。
* **包 (Packages)**: 使用小写字母，例如 ``qzen_core``。
* **类 (Classes)**: 使用帕斯卡命名法 (PascalCase)，例如 ``DocumentVector``。
* **函数与变量 (Functions & Variables)**: 使用蛇形命名法 (snake_case)，例如 ``calculate_similarity``。
* **常量 (Constants)**: 使用全大写字母和下划线，例如 ``SIMILARITY_THRESHOLD``。

文档字符串 (Docstrings)
============================

所有模块、类、方法和函数 **必须** 包含文档字符串。我们采用 **Google风格** 的docstring，因为它结构清晰且能被Sphinx的 ``napoleon`` 插件完美解析。

.. code-block:: python

   """模块的简要说明。

   这里可以写更详细的描述。
   """

   def calculate_hashes(root_path: str, file_extensions: list[str]) -> dict[str, str]:
       """计算指定目录下所有符合条件文件的哈希值。

       遍历根目录，对每个后缀在白名单内的文件计算其SHA-256哈希值。
       会跳过无法读取的文件。

       Args:
           root_path: 要扫描的根目录路径。
           file_extensions: 一个包含允许的文件后缀的列表 (例如 ['.pdf', '.docx'])。

       Returns:
           一个字典，键是文件的绝对路径，值是其SHA-256哈希值的十六进制字符串。
           如果目录不存在，则返回一个空字典。
       """
       # ... function body ...
       pass


注释
==================

遵循用户的偏好，非docstring的代码内部注释应使用中文。

.. code-block:: python

   # 遍历所有文本块，提取文本内容
   for block in page.get_text("blocks"):
       # block[4] 是文本内容
       text_content += block[4]

类型提示 (Type Hinting)
==========================

所有函数和方法的签名 **必须** 使用 `PEP 484 <https://www.python.org/dev/peps/pep-0484/>`_ 规定的类型提示。这极大地增强了代码的可读性，并允许静态代码分析工具（如PyCharm内置的检查器）发现潜在的类型错误。

.. code-block:: python

   from .document_model import Document

   def find_top_n_similar(target_doc: Document, all_docs: list[Document], n: int) -> list[Document]:
       # ... function body ...
       pass

API 设计指南
================

* **单一职责原则 (Single Responsibility Principle)**: 每个类和函数应该只做一件事，并把它做好。例如，一个类不应该既负责文件I/O，又负责UI更新。
* **接口分离**: UI层与业务逻辑层的交互应该是清晰且最小化的。UI层通过调用业务层暴露的公共方法来执行任务，业务层通过信号机制将结果异步地返回给UI层。
* **异常处理**: 显式地处理可能发生的异常（如 `FileNotFoundError`, `PermissionError`, 数据库连接失败等），并以友好的方式向用户报告错误或记录到日志中，而不是让程序崩溃。
* **使用日志**: 使用Python内置的 ``logging`` 模块来记录程序运行状态、调试信息和错误。避免在核心库代码中使用 ``print()`` 函数。