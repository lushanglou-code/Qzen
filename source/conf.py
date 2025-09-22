# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import os
import sys

from sphinx.ext.autosummary import autosummary_toc

# 告诉Sphinx你的项目代码在哪里 (从conf.py文件往上退一级到项目根目录)
sys.path.insert(0, os.path.abspath('..'))
# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Qzen'
copyright = '2025, LuZhao'
author = 'LuZhao'
release = 'y'

graphviz_dot_args = [
    '-Gcharset=utf8'  # <-- 强制 Graphviz 使用 UTF-8 编码处理文本 # #
]

# docs/source/conf.py

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',  # 核心：从docstrings自动生成文档
    'sphinx.ext.graphviz',
    'sphinx.ext.napoleon', # 支持Google/Numpy风格的docstring
    'sphinx.ext.autosummary', # 自动生成API文档
    'sphinx.ext.viewcode', # 在文档中添加源码链接
]

templates_path = ['_templates']
exclude_patterns = []

language = 'zh_CN'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

autosummary_generate = True #开启自动生成文件功能

# v3.3.3 修正: 必须将此项设为 True，以确保每次构建时都重新生成存根文件，
# 从而避免因代码中的 docstring 更新而导致与旧存根文件内容冲突，
# 这是解决“duplicate object description”警告的核心。
autosummary_generate_overwrite = True

# Napoleon 插件设置，确保 Google 风格的 docstrings 被正确解析
napoleon_google_docstring = True

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
