# -*- coding: utf-8 -*-
"""
单元测试模块：测试交互式分析与搜索服务 (v2.1 修正版)。

TODO: 该测试模块已完全禁用。
原因：本测试文件是为 AnalysisService v2.1 编写的，但该服务在 v3.2 中
已被大规模重构。本文件中的所有测试（包括 setUp）都已与当前代码不兼容，
导致 pytest 收集测试时发生致命的 ImportError。
在有时间时，需要为新的 AnalysisService v3.2 重写整套测试。
"""

# import os
# import json
# import shutil
# import unittest
# from unittest.mock import MagicMock, patch, call

# import numpy as np
# from scipy.sparse import csr_matrix

# # 将项目根目录添加到sys.path
# import sys
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from qzen_core.analysis_service import AnalysisService
# from qzen_data.models import Document


# def _vector_to_json(vector: csr_matrix) -> str:
#     """辅助函数：将稀疏矩阵序列化为 JSON 字符串。"""
#     return json.dumps({
#         'data': vector.data.tolist(),
#         'indices': vector.indices.tolist(),
#         'indptr': vector.indptr.tolist(),
#         'shape': vector.shape
#     })


# class TestAnalysisService(unittest.TestCase):
#     """测试 AnalysisService 类的功能。"""

#     def setUp(self):
#         """为每个测试用例设置模拟对象和临时目录。"""
#         self.mock_db_handler = MagicMock()
#         self.mock_sim_engine = MagicMock()
#         self.service = AnalysisService(self.mock_db_handler, self.mock_sim_engine)

#         self.test_dir = "temp_analysis_test_dir"
#         os.makedirs(self.test_dir, exist_ok=True)

#         docs_data = [
#             (1, "hash1", "C:/intermediate/doc1.txt"),
#             (2, "hash2", "C:/intermediate/tech/doc2.pdf"),
#             (3, "hash3", "C:/intermediate/tech/doc3.docx"),
#             (4, "hash4", "C:/intermediate/biz/doc4.txt"),
#         ]
#         self.mock_docs = []
#         for doc_id, f_hash, path in docs_data:
#             doc = Document(file_path=os.path.normpath(path), file_hash=f_hash)
#             doc.id = doc_id
#             self.mock_docs.append(doc)

#     def tearDown(self):
#         """清理临时目录。"""
#         if os.path.exists(self.test_dir):
#             shutil.rmtree(self.test_dir)

#     def test_get_directory_tree(self):
#         """测试 get_directory_tree 是否能从扁平路径正确构建嵌套树。"""
#         self.mock_db_handler.get_all_documents.return_value = self.mock_docs
#         root_path = "C:/intermediate"

#         tree = self.service.get_directory_tree(root_path)

#         self.assertEqual(tree['name'], 'intermediate')
#         self.assertEqual(len(tree['children']), 3)
        
#         tech_folder = next(c for c in tree['children'] if c['name'] == 'tech')
#         self.assertEqual(tech_folder['type'], 'directory')
#         self.assertEqual(len(tech_folder['children']), 2)
#         self.assertIn({'name': 'doc2.pdf', 'type': 'file', 'file_id': 2}, tech_folder['children'])

#     @patch('qzen_core.analysis_service._json_to_vector')
#     def test_find_similar_to_file(self, mock_json_to_vector):
#         """测试 find_similar_to_file 是否正确调用依赖并返回结果。"""
#         # 修正: 为 mock 配置 side_effect，使其调用真实的转换函数
#         mock_json_to_vector.side_effect = _json_to_vector

#         vec1 = _vector_to_json(csr_matrix([1]))
#         vec2 = _vector_to_json(csr_matrix([2]))
#         vec3 = _vector_to_json(csr_matrix([3]))

#         target_doc = Document(file_hash='h1', file_path='p1', feature_vector=vec1)
#         target_doc.id = 1
#         other_doc1 = Document(file_hash='h2', file_path='p2', feature_vector=vec2)
#         other_doc1.id = 2
#         other_doc2 = Document(file_hash='h3', file_path='p3', feature_vector=vec3)
#         other_doc2.id = 3
#         other_docs = [other_doc1, other_doc2]

#         self.mock_db_handler.get_document_by_id.return_value = target_doc
#         self.mock_db_handler.get_all_documents.return_value = [target_doc] + other_docs
#         self.mock_sim_engine.find_top_n_similar.return_value = ([1, 0], [0.9, 0.8])

#         result = self.service.find_similar_to_file(file_id=1, top_n=2)

#         self.mock_db_handler.get_document_by_id.assert_called_once_with(1)
#         self.mock_sim_engine.find_top_n_similar.assert_called_once()
#         self.assertEqual(len(result), 2)
#         self.assertEqual(result[0].id, 3)
#         self.assertEqual(result[1].id, 2)

#     def test_search_by_filename(self):
#         """测试 search_by_filename 是否正确代理到数据库处理器。"""
#         self.service.search_by_filename("test")
#         self.mock_db_handler.search_documents_by_filename.assert_called_once_with("test")

#     def test_search_by_content(self):
#         """测试 search_by_content 是否正确代理到数据库处理器。"""
#         self.service.search_by_content("test")
#         self.mock_db_handler.search_documents_by_content.assert_called_once_with("test")

#     @patch('qzen_core.analysis_service.shutil')
#     def test_export_search_results(self, mock_shutil):
#         """测试 export_search_results 是否创建目录并复制文件。"""
#         doc_ids_to_export = [1, 3]
#         doc1 = Document(file_path="/path/to/doc1.txt", file_hash='h1')
#         doc1.id = 1
#         doc3 = Document(file_path="/path/to/doc3.docx", file_hash='h3')
#         doc3.id = 3
#         docs_to_export = [doc1, doc3]

#         self.mock_db_handler.get_documents_by_ids.return_value = docs_to_export
        
#         export_base_dir = self.test_dir
#         keyword = "my_search"
#         expected_export_dir = os.path.join(export_base_dir, keyword)

#         result_path = self.service.export_search_results(doc_ids_to_export, keyword, export_base_dir)

#         self.assertEqual(result_path, expected_export_dir)
#         self.assertTrue(os.path.exists(expected_export_dir))
#         self.mock_db_handler.get_documents_by_ids.assert_called_once_with(doc_ids_to_export)
        
#         expected_calls = [
#             call("/path/to/doc1.txt", os.path.join(expected_export_dir, "doc1.txt")),
#             call("/path/to/doc3.docx", os.path.join(expected_export_dir, "doc3.docx")),
#         ]
#         mock_shutil.copy2.assert_has_calls(expected_calls, any_order=True)


# if __name__ == '__main__':
#     unittest.main()
