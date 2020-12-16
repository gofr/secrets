#!/usr/bin/env python3

import argparse
import binascii
import base64
import io
import os
import re

import commonmark
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image


class HTMLRenderer(commonmark.HtmlRenderer):
    """Extra safe HTML renderer.

    I'm using this in a tool where I encrypt and publish the rendered content.
    I don't want to have to parse image tags and arbitrary HTML content nested
    in the CommonMark to make sure they don't include extra content that would
    need including and encrypting. Even including external content like images
    potentially leaks information.

    When the "safe" option is set to True:
    * don't render HTML content at all and
    * render only the alt text of images, but do render CommonMark nested in
      that alt text in this case.

    Safe mode is the default.

    While I'm at it, get rid of obsolete, self-closing tag syntax.
    """
    def __init__(self, options=None):
        options = options or {}
        options.setdefault('safe', True)
        super().__init__(options)

    def tag(self, name, attrs=None, selfclosing=None):
        # Self-closing tags don't exist in HTML:
        super().tag(name, attrs, False)

    def image(self, node, entering):
        # Don't render the image at all in safe mode, only the alt text,
        # but allow tags in that text in that case.
        if not self.options.get('safe'):
            if entering:
                if self.disable_tags == 0:
                    self.lit(f'<img src="{self.escape(node.destination)}" alt="')
                self.disable_tags += 1
            else:
                self.disable_tags -= 1
                if self.disable_tags == 0:
                    if node.title:
                        self.lit(f'" title="{self.escape(node.title)}')
                    self.lit('">')

    # TODO: Enable this again? But then use beautifulsoup4 to parse it and
    # filter out bad stuff like <script> and <img> and event attributes?
    # Or whitelist certain things?
    def html_inline(self, node, entering):
        if not self.options.get('safe'):
            super().html_inline(node, entering)

    def html_block(self, node, entering):
        if not self.options.get('safe'):
            super().html_block(node, entering)


# TODO: unittest this class.
class Post:
    _metadata_pattern = re.compile(
        r'^(?:(?P<key>[a-z0-9_]+): (?P<value>.+)|# .*||(?P<error>.*))$',
        re.MULTILINE)

    def __init__(self, file_path):
        with open(file_path, 'rt') as f:
            sections = re.split(r'\n\n---\n', f.read(), flags=re.MULTILINE)

        metadata = {}
        parsed_sections = []
        if sections[0].startswith('---\n'):
            # Parse the first section, without the leading "---\n":
            metadata = self.parse_metadata(sections.pop(0)[4:])
        for section in sections:
            match = re.match(self._metadata_pattern, section)
            if match and match.group('key'):
                parsed_sections.append(self.parse_metadata(section))
            elif not section.strip():
                continue
            else:
                parsed_sections.append(self.parse_commonmark(section))
        self.location = os.path.dirname(file_path)
        self.sections = parsed_sections
        self.title = metadata.get('title')

    def parse_commonmark(self, content):
        """Parse CommonMark and return rendered HTML."""
        parser = commonmark.Parser()
        renderer = HTMLRenderer()
        return renderer.render(parser.parse(content))

    def parse_metadata(self, content):
        """Parse key-value string and return dict."""
        data = {}
        for match in re.finditer(self._metadata_pattern, content):
            key = match.group('key')
            error = match.group('error')
            if key is not None:
                if data.get(key):
                    raise ValueError(f'Duplicate "{key}" key name in line:\n{match.group(0)}')
                else:
                    data[key] = match.group('value')
            elif error:
                raise ValueError(f'Invalid key-value data in line:\n{match.group(0)}')
        return data

    # TODO: This needs a lot of cleanup:
    # * Create a separate Blog class that holds info like the template dir.
    # * Don't rewrite the sections in the Post object.
    # * Move encryption elsewhere?
    def write(self, output_dir, template_dir, key):
        env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=select_autoescape()
        )
        encrypted_images = {}
        for index, section in enumerate(self.sections):
            if isinstance(section, dict) and 'image' in section:
                abs_path = os.path.abspath(os.path.join(self.location, section['image']))
                if abs_path not in encrypted_images:
                    img_name = get_random_name()
                    encrypted_images[abs_path] = img_name
                    with open(abs_path, 'rb') as img_handle:
                        img = Image.open(img_handle)
                        encrypt(get_clean_image_data(img), key, os.path.join(output_dir, img_name))
                section['image'] = encrypted_images[abs_path]
        template = env.get_template('content.html')
        content = template.render(content=self.sections)
        encrypt(content.encode(), key, os.path.join(output_dir, 'content'))
        template = env.get_template('article.html')
        with open(os.path.join(output_dir, 'index.html'), 'w') as index_file:
            content = template.render(title=self.title)
            index_file.write(content)


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


def package(input_file, base_dir, create_dir, template_dir, key=None):
    if create_dir:
        new_dir = create_random_subdir(base_dir)
    else:
        new_dir = base_dir

    if key is None:
        key = AESGCM.generate_key(bit_length=128)
    post = Post(input_file)
    post.write(new_dir, template_dir, key)
    return new_dir, key


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="""\
        Convert a content input file to HTML and encrypt both it and any
        media files it references. The encrypted content can be stored in a
        new, randomly-named directory or a pre-existing one.
        """)
    parser.add_argument('input', help='path to content file to encrypt')
    parser.add_argument(
        '--template-dir', default='templates',
        help='path to directory containing templates')
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
        args.input, output_dir, create_dir, args.template_dir, args.key)
    base64key = base64.b64encode(key).decode()
    print(f'dir={new_dir}\nkey={base64key}')
