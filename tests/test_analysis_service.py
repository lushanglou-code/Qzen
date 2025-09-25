# -*- coding: utf-8 -*-
"""
单元测试模块：测试交互式分析与搜索服务 (v4.3 验证版)。

此版本新增了一个针对 v4.3 修复的单元测试，以确保 `find_similar_to_file`
方法始终通过稳定的数据库 ID 而非不稳定的文件路径来调用核心业务逻辑，
从而验证了关键 Bug 的修复。
"""

import os
import unittest
from unittest.mock import MagicMock, patch, call

# 将项目根目录添加到sys.path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from qzen_core.analysis_service import AnalysisService
from qzen_data.models import Document

class TestAnalysisService(unittest.TestCase):
    """测试 AnalysisService 类的功能。"""

    def setUp(self):
        """为每个测试用例设置模拟的依赖项。"""
        self.mock_db_handler = MagicMock()
        self.mock_orchestrator = MagicMock()
        self.service = AnalysisService(self.mock_db_handler, self.mock_orchestrator)

    def test_find_similar_to_file_delegates_to_orchestrator(self):
        """
        测试 find_similar_to_file 是否正确地预热引擎并调用 Orchestrator。
        """
        # --- Arrange ---
        test_file_id = 123
        test_top_n = 15
        mock_is_cancelled = lambda: False
        expected_results = [{'id': 4, 'path': '/path/to/doc4.txt', 'score': 0.99}]

        # 配置模拟对象的返回值
        self.mock_orchestrator.find_top_n_similar_for_file.return_value = expected_results

        # --- Act ---
        results = self.service.find_similar_to_file(
            file_id=test_file_id, 
            top_n=test_top_n, 
            is_cancelled_callback=mock_is_cancelled
        )

        # --- Assert ---
        # 1. 验证它首先尝试预热引擎
        self.mock_orchestrator.prime_similarity_engine.assert_called_once_with(is_cancelled_callback=mock_is_cancelled)
        
        # 2. 验证它随后调用了 orchestrator 的核心方法，并传递了正确的参数
        self.mock_orchestrator.find_top_n_similar_for_file.assert_called_once_with(
            target_file_id=test_file_id, 
            n=test_top_n, 
            is_cancelled_callback=mock_is_cancelled
        )

        # 3. 验证它返回了来自 orchestrator 的结果
        self.assertEqual(results, expected_results)

    def test_find_similar_correctly_uses_file_id_after_fix(self):
        """
        v4.3 验证: 确保 find_similar_to_file 始终使用数据库 ID 调用 Orchestrator。

        此测试明确验证 v4.3 的修复：服务层将从 UI 接收到的稳定文件 ID
        直接、正确地传递给业务逻辑层。这是解决因外部文件路径与内部
        （中间）文件路径不匹配而导致“文件未找到”错误的核心。
        """
        # --- Arrange ---
        test_file_id = 999  # 模拟一个来自UI的请求，UI只知道数据库ID
        test_top_n = 5
        mock_is_cancelled = lambda: False
        
        # --- Act ---
        self.service.find_similar_to_file(
            file_id=test_file_id, 
            top_n=test_top_n,
            is_cancelled_callback=mock_is_cancelled
        )

        # --- Assert ---
        # 验证 AnalysisService 是否将这个 ID 原封不动地传递给了 Orchestrator
        self.mock_orchestrator.find_top_n_similar_for_file.assert_called_once_with(
            target_file_id=test_file_id,
            n=test_top_n,
            is_cancelled_callback=mock_is_cancelled
        )

    @patch('qzen_core.analysis_service.shutil')
    @patch('qzen_core.analysis_service.os')
    def test_export_files_by_ids(self, mock_os, mock_shutil):
        """
        测试通用的 export_files_by_ids 方法的核心逻辑。
        """
        # --- Arrange ---
        doc_ids_to_export = [1, 3]
        destination_dir = "/export/here"
        
        doc1 = Document(id=1, file_path="/path/to/doc1.txt")
        doc3 = Document(id=3, file_path="/path/to/doc3.docx")
        docs_from_db = [doc1, doc3]

        self.mock_db_handler.get_documents_by_ids.return_value = docs_from_db
        mock_os.path.basename.side_effect = os.path.basename
        mock_os.path.join.side_effect = os.path.join

        # --- Act ---
        result_path = self.service.export_files_by_ids(doc_ids_to_export, destination_dir)

        # --- Assert ---
        # 1. 验证它创建了目标目录
        mock_os.makedirs.assert_called_once_with(destination_dir, exist_ok=True)

        # 2. 验证它从数据库获取了正确的文档信息
        self.mock_db_handler.get_documents_by_ids.assert_called_once_with(doc_ids_to_export)

        # 3. 验证它为每个文件调用了复制操作
        expected_calls = [
            call("/path/to/doc1.txt", os.path.join(destination_dir, "doc1.txt")),
            call("/path/to/doc3.docx", os.path.join(destination_dir, "doc3.docx")),
        ]
        mock_shutil.copy2.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(mock_shutil.copy2.call_count, 2)

        # 4. 验证它返回了目标目录的路径
        self.assertEqual(result_path, destination_dir)

    @patch('qzen_core.analysis_service.AnalysisService.export_files_by_ids')
    @patch('qzen_core.analysis_service.os')
    def test_export_search_results_delegates_correctly(self, mock_os, mock_export_files):
        """
        测试 export_search_results 是否能正确生成目录名并调用通用导出方法。
        """
        # --- Arrange ---
        doc_ids = [10, 20]
        keyword = "test keyword"
        base_dir = "/base/export"
        
        # 模拟 os.path.join 和 os.path.normpath 的行为
        mock_os.path.join.side_effect = os.path.join
        mock_os.path.normpath.side_effect = os.path.normpath
        
        expected_export_dir = os.path.normpath(os.path.join(base_dir, f"关键词_{keyword}"))
        mock_progress = MagicMock()
        mock_is_cancelled = MagicMock()

        # --- Act ---
        self.service.export_search_results(doc_ids, keyword, base_dir, mock_progress, mock_is_cancelled)

        # --- Assert ---
        # 验证核心委托：调用了通用的 export_files_by_ids 方法，并传递了正确构造的路径
        mock_export_files.assert_called_once_with(
            doc_ids, 
            expected_export_dir, 
            mock_progress, 
            mock_is_cancelled
        )

    def test_search_by_filename_delegates_to_db_handler(self):
        """
        测试 search_by_filename 是否正确地将调用代理到数据库处理器。
        """
        keyword = "test_file"
        self.service.search_by_filename(keyword)
        self.mock_db_handler.search_documents_by_filename.assert_called_once_with(keyword)

    def test_search_by_content_delegates_to_db_handler(self):
        """
        测试 search_by_content 是否正确地将调用代理到数据库处理器。
        """
        keyword = "test_content"
        self.service.search_by_content(keyword)
        self.mock_db_handler.search_documents_by_content.assert_called_once_with(keyword)

if __name__ == '__main__':
    unittest.main()
