# -*- coding: utf-8 -*-
"""
数据访问层 (DAL) 包。提供对文件系统和数据库的统一访问接口。
"""

# 导入模块以使其能被 autosummary 发现
from . import database_handler
from . import file_handler
from . import models