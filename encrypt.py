#!/usr/bin/env python3

import argparse
import binascii
import base64
import copy
import io
import json
import os
import re
import textwrap

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
class Blog:
    CONFIG_NAME = 'secrets.json'  # Name of file in the input_dir

    def __init__(self, input_dir):
        self.input_dir = input_dir
        self.config = None
        self.load_config()
        posts = {}
        for filename in os.listdir(input_dir):
            if filename.endswith('.md'):
                posts[filename] = Post(os.path.join(input_dir, filename))
        self.posts = posts

    def load_config(self):
        try:
            with open(os.path.join(self.input_dir, self.CONFIG_NAME)) as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {}

    def write_config(self):
        # TODO: Create a backup? During development I accidentally added a non-
        # serializable object to the dict. This raised an exception while dumping.
        # The resulting invalid JSON file was only written up to the invalid value.
        # If that happens again I'll lose everything that still needed to be
        # written afterwards. If this includes encryption keys I can lose access to
        # content. I need to either make the update atomic (create new file and then
        # overwrite the original), handle errors in some way or create a backup.
        with open(os.path.join(self.input_dir, self.CONFIG_NAME), 'w') as f:
            json.dump(self.config, f, indent=4)

    def write(self, output_dir, template_dir):
        for filename, post in self.posts.items():
            # TODO: What do I do with posts that are listed in the config but
            # don't have any corresponding file?
            post_config = self.config.setdefault(filename, {})
            # TODO: What if someone wants to publish a blog in two different
            # places with different dirs/keys? Should the config go in the
            # output_dir instead? But it should definitely not be made public!
            if 'dir' in post_config:
                # BUG: The value in the JSON already includes the output dir
                # that was used to create it previously. If I prepend it again
                # I end up with a non-existent dir. Even if I had not prepended
                # it before there's no guarantee that that dir still exists.
                # If I don't prepend it I will write outside the intended
                # output_dir (if it is different from the previous one).
                out_dir = os.path.join(output_dir, post_config['dir'])
            else:
                out_dir = create_random_subdir(output_dir)
            if 'key' in post_config:
                # NOTE: This can raise argparse.ArgumentTypeError, which is strange here.
                key = valid_encryption_key(post_config['key'])
            else:
                key = AESGCM.generate_key(bit_length=128)
            # Update the config before writing the encrypted files. Otherwise
            # I could end up with encrypted content I don't have a key for.
            # NOTE: I always write the config even if it didn't change.
            # Is this less error prone?
            self.config[filename].update(dir=out_dir, key=base64.b64encode(key).decode())
            self.write_config()
            # NOTE: I re-encrypt the content without looking if maybe the output
            # already existed. Re-encrypting may be unnecessary but is hard
            # to avoid since it's hard to determine if any of the content or
            # templates changed, especially with my output being encrypted.
            # Secondly, since image files are stored with new random names, this
            # will leave behind now unused files from previous rounds.
            post.write(out_dir, template_dir, key)


# TODO: unittest this class.
class Post:
    _metadata_pattern = re.compile(
        r'^(?:(?P<key>[a-z0-9_]+): (?P<value>.+)|# .*||(?P<error>.*))$',
        re.MULTILINE)

    # TODO: Require a post to be associated with a Blog? In that case I can set
    # global options on the blog that get used by posts.
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

    # TODO: Move encryption elsewhere?
    def write(self, output_dir, template_dir, key):
        env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=select_autoescape()
        )
        encrypted_images = {}
        copied_sections = copy.deepcopy(self.sections)
        for section in copied_sections:
            if isinstance(section, dict) and 'image' in section:
                abs_path = os.path.abspath(os.path.join(self.location, section['image']))
                if abs_path not in encrypted_images:
                    img_name = get_random_file_name()
                    encrypted_images[abs_path] = img_name
                    encrypt(get_clean_image_data(abs_path), key, os.path.join(output_dir, img_name))
                section['image'] = encrypted_images[abs_path]
        content_template = env.get_template('content.html')
        content = content_template.render(content=copied_sections)
        encrypt(content.encode(), key, os.path.join(output_dir, 'content'))
        post_template = env.get_template('article.html')
        with open(os.path.join(output_dir, 'index.html'), 'w') as index_file:
            post = post_template.render(title=self.title)
            index_file.write(post)


def get_random_file_name():
    # Base32 to be compatible with case-insensitive file systems:
    return base64.b32encode(os.urandom(10)).decode().strip('=').lower()


def create_random_subdir(base_path):
    """Create directory with random name in `base_path` and return path."""
    path = os.path.join(base_path, get_random_file_name())
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


def get_clean_image_data(image_path):
    """Return (cleaned-up) image data bytes given the path to a JPEG image.

    If the image was a JPEG file, return the image data converted to a
    progressive JPEG re-compressed with settings similar to the original, with
    EXIF metadata dropped. PIL cannot do lossless JPEG operations.

    Otherwise, raise a TypeError.
    """
    image = Image.open(image_path)
    if image.format != 'JPEG':
        raise TypeError('Only JPEG images are supported')
    tmp = io.BytesIO()
    try:
        image.save(tmp, format='JPEG', quality='keep', progressive=True)
        return tmp.getvalue()
    finally:
        tmp.close()


# TODO: My publishing is incomplete. I don't include the shared JS/CSS etc.
# that's needed to be able to view it. Should publishing involve creating
# the whole structure, not just the encrypted content? Probably.
def publish(input_dir, output_dir, template_dir):
    blog = Blog(input_dir)
    blog.write(output_dir, template_dir)


if __name__ == '__main__':
    class RawDescriptionAndDefaultsHelpFormatter(
            argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(
        formatter_class=RawDescriptionAndDefaultsHelpFormatter,
        description=textwrap.dedent("""\
        Create a secret, encrypted blog

        This tool parses all the .md files in the specified input directory
        according to the format described in content-format.md. It then renders
        each .md file as a basic HTML file in a randomly-named subfolder inside
        the specified output directory, with the post text and images encrypted.

        A file called secrets.json is created (or updated) inside the input
        directory that maps the original .md filename to the name of its
        output folder and the encryption key that was used. Each folder is
        encrypted with a different key. All content in one folder uses the same
        key but a different IV.

        The resulting output can be hosted anywhere that supports static content
        and HTTPS. To load the decrypted content, use the encryption key as the
        hash. E.g. https://your.host/randomdirname/#theencryptionkey

        The key is not sent to the server in this way, but this is clearly not
        very secure for at least two reasons:
        * Anyone you share a link with will have the encryption key and can
          decrypt the content you shared with them. They might accidentally or
          deliberately share that link with others.
        * This method is not host-proof. It would be possible for your host to
          acquire the encryption key even if it isn't normally sent to them.

        The decryption happens on the client side using the Web Crypto API:
        https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API

        As that documentation states:

        "If you're not sure you know what you are doing, you probably shouldn't
        be using this API."

        I don't know what I'm doing. Don't use this tool for anything serious.
        """))
    parser.add_argument('input_dir', help='path to directory with blog content')
    parser.add_argument('output_dir', help='path to directory to write encrypted content to')
    parser.add_argument(
        '--template-dir', default='templates',
        help='path to directory containing templates')

    args = parser.parse_args()
    publish(args.input_dir, args.output_dir, args.template_dir)
