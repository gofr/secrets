import json
import math
import tempfile
import unittest

import commonmark
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import secretblog.utils as utils


class TestHTMLRenderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = commonmark.Parser()

    def _render_html(self, commonmark, options=None):
        renderer = utils.HTMLRenderer(options=options)
        return renderer.render(self.parser.parse(commonmark))

    def test_no_self_closing_tags(self):
        result = self._render_html("---")
        self.assertEqual(result, "<hr>\n")

    def test_no_self_closing_unsafe_image(self):
        result = self._render_html(
            "![text](url)",
            options={"safe": False})
        self.assertEqual(result, '<p><img src="url" alt="text"></p>\n')

    def test_safe_image_is_text(self):
        result = self._render_html("![text](url)")
        self.assertEqual(result, "<p>text</p>\n")

    def test_safe_image_can_have_nested_tags(self):
        result = self._render_html("![*text* with `code`](url)")
        self.assertEqual(result, "<p><em>text</em> with <code>code</code></p>\n")

    def test_inline_html_is_stripped(self):
        result = self._render_html('foo <a href="http://www.example.com"><i>bar</i></a>')
        self.assertEqual(result, "<p>foo bar</p>\n")

    def test_inline_script_is_stripped(self):
        result = self._render_html('foo <script>alert("bad!")</script> baz')
        self.assertEqual(result, "<p>foo alert(&quot;bad!&quot;) baz</p>\n")

    def test_html_block_is_removed(self):
        result = self._render_html(
            "foo\n\n<table><tr><td>cell</td></tr></table>\n\nbar")
        self.assertEqual(result, "<p>foo</p>\n<p>bar</p>\n")

    def test_script_block_is_removed(self):
        result = self._render_html('foo\n\n<script>alert("bad!")</script>\n\nbar')
        self.assertEqual(result, "<p>foo</p>\n<p>bar</p>\n")


class TestCipher(unittest.TestCase):
    def test_decode_key_too_few_bits(self):
        with self.assertRaisesRegex(ValueError, "must be 256 bit"):
            utils.Cipher("a" * math.ceil(128 / 6))

    def test_decode_key_too_many_bits(self):
        with self.assertRaisesRegex(ValueError, "must be 256 bit"):
            utils.Cipher("a" * math.ceil(512 / 6))

    def test_decode_valid_key(self):
        decoded = utils.Cipher("a" * math.ceil(256 / 6)).key
        self.assertIsInstance(decoded, bytes)
        self.assertEqual(len(decoded), 32)

    def test_decode_key_base64_decode_error(self):
        with self.assertRaisesRegex(ValueError, "Invalid base64-encoded string") as ctx:
            utils.Cipher("-invalid-")
        self.assertIsNone(ctx.exception.__cause__)

    def test_encryption(self):
        key = b"a" * 32
        secret = b"test"
        with tempfile.NamedTemporaryFile("rb") as f:
            utils.Cipher(key).encrypt(secret, f.name)
            encrypted = f.read()
        aesgcm = AESGCM(key)
        self.assertEqual(aesgcm.decrypt(encrypted[0:12], encrypted[12:], None), secret)

    def test_stringification(self):
        key = "A" * math.ceil(256 / 6)
        self.assertEqual(str(utils.Cipher(key)), key)


class TestJSONConfig(unittest.TestCase):
    def test_decode_posts_default(self):
        config = json.loads("{}", cls=utils.JSONConfigDecoder)
        self.assertIn("posts", config)

    def test_decode_posts_config(self):
        config = json.loads('{"posts": {"foo": "bar"}}', cls=utils.JSONConfigDecoder)
        self.assertIn("posts", config)
        self.assertIn("foo", config["posts"])

    def test_decode_invalid_key(self):
        with self.assertRaisesRegex(ValueError, "^Invalid"):
            json.loads('{"key": "12345"}', cls=utils.JSONConfigDecoder)

    def test_decode_valid_key(self):
        key = "a" * math.ceil(256 / 6)
        config = json.loads(f'{{"key": "{key}"}}', cls=utils.JSONConfigDecoder)
        self.assertIsInstance(config["key"], utils.Cipher)

    def test_encode_key(self):
        key = "A" * math.ceil(256 / 6)
        config = json.dumps({"key": utils.Cipher(key)}, cls=utils.JSONConfigEncoder)
        self.assertEqual(config, f'{{"key": "{key}"}}')
