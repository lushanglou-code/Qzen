# -*- coding: utf-8 -*-
"""
独立测试 dmPython 数据库连接。
"""
import dmPython
import sys

# 请根据您的实际数据库信息修改以下参数
DB_HOST = "127.0.0.1"
DB_PORT = 5236
DB_USER = "GIMI"
DB_PASSWORD = "DM8DM8DM8"

try:
    # 尝试建立连接
    conn = dmPython.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        server=DB_HOST,
        port=DB_PORT
    )
    print("dmPython 连接成功！")

    # 尝试执行一个简单查询
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM DUAL")
    result = cursor.fetchone()
    print(f"查询结果: {result}")

    cursor.close()
    conn.close()
    print("dmPython 连接已关闭。")

except dmPython.Error as e:
    print(f"dmPython 连接失败: {e}")
    print("请检查：")
    print("1. 达梦数据库服务是否正在运行。")
    print("2. 数据库主机、端口、用户名、密码是否正确。")
    print("3. 达梦客户端库（DLLs）是否已安装，并且其路径已添加到系统 PATH 环境变量中。")
    print("4. Python 解释器与达梦客户端库的位数是否匹配（32位 vs 64位）。")
    sys.exit(1)
except Exception as e:
    print(f"发生未知错误: {e}")
    sys.exit(1)
