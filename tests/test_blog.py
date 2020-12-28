import unittest

import blog


class TestPost(unittest.TestCase):
    def test_load_doesnt_override_unset_title(self):
        post = blog.Post()
        post.load('---\ntitle: title\n\n---\ncontent')
        self.assertIsNone(post.title)
        self.assertEqual(len(post._sections), 1)

    def test_load_doesnt_override_set_title(self):
        post = blog.Post(title='original')
        post.load('---\ntitle: title\n\n---\ncontent')
        self.assertEqual(post.title, 'original')
        self.assertEqual(len(post._sections), 1)

    def test_load_with_title_override(self):
        post = blog.Post()
        post.load('---\ntitle: title\n\n---\ncontent', override_title=True)
        self.assertEqual(post.title, 'title')
        self.assertEqual(len(post._sections), 1)

    def test_load_without_title(self):
        post = blog.Post(title='title')
        post.load('content')
        self.assertEqual(post.title, 'title')
        self.assertEqual(len(post._sections), 1)

    def test_load_with_invalid_separators(self):
        post = blog.Post()
        post.load('content\n--\n---\n----\nmore\n \n---\n')
        self.assertEqual(len(post._sections), 1)
