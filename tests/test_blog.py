import os
import unittest
from unittest.mock import Mock

import secretblog.blog as blog


class TestBlog(unittest.TestCase):
    def test_create_from_empty_dir(self):
        os.scandir = Mock()
        os.scandir.return_value = []

        b = blog.Blog('input', 'output', 'assets')
        self.assertEqual(b.asset_dir, 'assets')
        self.assertEqual(b.input_dir, 'input')
        self.assertEqual(b.output_dir, 'output')
        self.assertEqual(b.config, {"posts": {}})
        self.assertEqual(b.posts, {})

    def test_create_from_dir(self):
        test_dir = Mock()
        test_dir.is_dir.return_value = True
        test_dir.is_file.return_value = False
        test_dir.name = "foo"
        test_dir.path = "/bar/foo"
        test_file = Mock()
        test_file.is_dir.return_value = False
        test_file.is_file.return_value = True
        test_file.name = "text.md"
        test_file.path = "/bar/foo/text.md"
        os.scandir = Mock()
        os.scandir.return_value = [test_dir, test_file]

        b = blog.Blog('input', 'output', 'assets')
        self.assertIn(test_dir.name, b.posts)
        post = b.posts[test_dir.name]
        self.assertEqual(post.path, test_dir.path)
        self.assertEqual(len(post.content), 1)
        content = post.content[0]
        self.assertEqual(content.text.path, test_file.path)
        self.assertIsNone(content.media)
        self.assertEqual(content.post, post)
