#!/usr/bin/env python3

import argparse
import binascii
import base64
import io
import os

import commonmark
from commonmark.render.html import potentially_unsafe
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageOps


class HTMLRenderer(commonmark.HtmlRenderer):
    def tag(self, name, attrs=None, selfclosing=None):
        # Self-closing tags don't exist in HTML:
        super().tag(name, attrs, False)

    def image(self, node, entering):
        if entering:
            if self.disable_tags == 0:
                if (not node.destination or
                        self.options.get('safe') and potentially_unsafe(node.destination)):
                    self.lit('<img src="" alt="')
                else:
                    self.lit(f'<img src="{self.escape(node.destination)}" alt="')
            self.disable_tags += 1
        else:
            self.disable_tags -= 1
            if self.disable_tags == 0:
                self.lit('"')
                if node.list_data:
                    self.lit(''.join([
                        f' {attr}="{self.escape(value)}"' for attr, value in node.list_data.items()
                    ]))
                if node.title:
                    self.lit(f' title="{self.escape(node.title)}"')
                self.lit('>')


def get_random_name():
    return base64.b64encode(os.urandom(9), altchars=b'-_').decode()


def create_random_subdir(base_path):
    """Create directory with random name in `base_path` and return path."""
    path = os.path.join(base_path, get_random_name())
    os.mkdir(path)
    return path


def valid_encryption_key(base64key):
    prefix = 'Invalid base64-encoded encryption key:'
    try:
        key = base64.b64decode(base64key, validate=True)
        if len(key) == 16:
            return key
        else:
            raise argparse.ArgumentTypeError(f'{prefix} Key must be 128 bit')
    except binascii.Error as e:
        raise argparse.ArgumentTypeError(f'{prefix} {e}')


def encrypt(data, key, output_file):
    """Write `data` bytes encrypted with 128-bit AES-GCM using `key` to `output_file`."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96 random bits
    with open(output_file, 'wb') as output_object:
        output_object.write(
            nonce + aesgcm.encrypt(nonce, data, None))


def thumbnail(image, size):
    """Return bytes containing a resized copy of `image` as JPEG.

    `size` should be a (width, height) tuple.
    """
    thumb = ImageOps.fit(image, size)
    tmp = io.BytesIO()
    try:
        thumb.save(tmp, 'JPEG', quality=85, progressive=True)
        return tmp.getvalue()
    finally:
        tmp.close()


def get_clean_image_data(image):
    """Return (cleaned-up) bytes given a PIL.Image object of a JPEG image.

    If the image object was a JPEG file, return the image data losslessly
    converted to progressive and with EXIF metadata dropped.

    Otherwise, raise a TypeError.
    """
    if image.format != 'JPEG':
        raise TypeError('Only JPEG images are supported')
    tmp = io.BytesIO()
    try:
        image.save(tmp, format='JPEG', quality='keep', progressive=True)
        return tmp.getvalue()
    finally:
        tmp.close()


def encrypt_images(commonmark_ast, key, input_dir, output_dir):
    """Encrypt images mentioned in `commonmark_ast` and update the AST.

    Use `key` for the encryption.
    Use `input_dir` as the base directory to resolve relative image paths.
    Store the encrypted images with a random name but the original file
    extension in `output_dir`.
    """
    for current, entering in commonmark_ast.walker():
        # Absolute URLs contain ":". Ignore those.
        if current.t == 'image' and entering and ':' not in current.destination:
            old_path = os.path.join(input_dir, current.destination)
            full_name = get_random_name()
            thumb_name = get_random_name()
            thumb_size = (320, 180)
            with open(old_path, 'rb') as image:
                img = Image.open(image)
                encrypt(thumbnail(img, thumb_size), key, os.path.join(output_dir, thumb_name))
                encrypt(get_clean_image_data(img), key, os.path.join(output_dir, full_name))
            current.list_data = {
                'width': str(thumb_size[0]),
                'height': str(thumb_size[1]),
                'data-thumbnail': thumb_name,
                'data-src': full_name,
                'data-type': img.get_format_mimetype()
            }
            current.destination = None


def write_article(output_dir, template_dir, title=None, thumbnail=None):
    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=select_autoescape()
    )
    template = env.get_template('article.html')
    with open(os.path.join(output_dir, 'index.html'), 'w') as index_object:
        content = template.render(title=title, thumbnail=thumbnail)
        index_object.write(content)


def package(
        input_file, base_dir, create_dir, template_dir,
        title, thumbnail, key=None):
    if create_dir:
        new_dir = create_random_subdir(base_dir)
    else:
        new_dir = base_dir

    if key is None:
        key = AESGCM.generate_key(bit_length=128)
    with open(input_file) as cm:
        text_content = cm.read()
    parser = commonmark.Parser()
    ast = parser.parse(text_content)
    encrypt_images(ast, key, os.path.dirname(input_file), new_dir)
    renderer = HTMLRenderer()
    html_content = renderer.render(ast)
    encrypt(html_content.encode(), key, os.path.join(new_dir, 'content'))
    write_article(new_dir, template_dir, title, thumbnail)
    return new_dir, key


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="""\
        Convert a CommonMark input file to HTML and encrypt both it and any
        media files it references. The encrypted content can be stored in a
        new, randomly-named directory or a pre-existing one.
        """)
    parser.add_argument('input', help='path to CommonMark file to encrypt')
    parser.add_argument(
        '--template-dir', default='templates',
        help='path to directory containing templates')
    parser.add_argument(
        '--thumbnail', help="""\
            path to image file that will be used unencrypted as a thumbnail
            for Facebook""")
    parser.add_argument('--title', help='title to use for Facebook')
    parser.add_argument('--key', type=valid_encryption_key, help="""\
        existing base64-encoded, 128-bit encryption key to use instead of
        generating a new one""")

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        '--base-dir', default='.', help="""\
            path to output base directory. The encrypted files are stored in a
            new, randomly named directory inside this. Mutually exclusive with
            --output-dir.""")
    output_group.add_argument(
        '--output-dir', help="""\
            path to output directory. The encrypted files are stored directly
            in this directory. Mutually exclusive with --base-dir.""")

    args = parser.parse_args()

    output_dir = args.output_dir or args.base_dir
    create_dir = (args.output_dir is None)

    new_dir, key = package(
        args.input, output_dir, create_dir,
        args.template_dir, args.title, args.thumbnail, args.key)
    base64key = base64.b64encode(key).decode()
    print(f'dir={new_dir}\nkey={base64key}')
