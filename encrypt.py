#!/usr/bin/env python3

import argparse
import binascii
import base64
import copy
import io
import json
import os
import re
import shutil
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
                posts[filename] = Post.from_file(os.path.join(input_dir, filename))
        self.posts = posts

    def load_config(self):
        try:
            with open(os.path.join(self.input_dir, self.CONFIG_NAME)) as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {}

    def write_config(self):
        # NOTE: It's quite important not to lose the config since it holds
        # encryption keys. This is reasonably safe now, but not thread-safe.
        config_file = os.path.join(self.input_dir, self.CONFIG_NAME)
        # Dump to string to find errors early and not end up with a corrupt file:
        config = json.dumps(self.config, indent=4)
        try:
            # Move the old config out of the way, replacing the old backup.
            os.replace(config_file, config_file + '.bak')
        except FileNotFoundError:
            pass  # There was nothing to move.
        # Now write the new file:
        with open(config_file, 'x') as f:
            f.write(config)

    def write(self, output_dir, template_dir):
        # TODO: Do something less hacky. And allow output dir to exist?
        shutil.copytree(
            os.path.join(self.input_dir, os.pardir, 'www'),
            output_dir)
        for filename, post in self.posts.items():
            # TODO: What do I do with posts that are listed in the config but
            # don't have any corresponding file?
            post_config = self.config.setdefault(filename, {})
            # TODO: What if someone wants to publish a blog in two different
            # places with different dirs/keys? Should the config go in the
            # output_dir instead? But it should definitely not be made public!
            if 'dir' in post_config:
                post_dir = post_config['dir']
            else:
                post_dir = get_random_file_name()
            if 'key' in post_config:
                # NOTE: This can raise argparse.ArgumentTypeError, which is strange here.
                key = valid_encryption_key(post_config['key'])
            else:
                key = AESGCM.generate_key(bit_length=128)
            # Update the config before writing the encrypted files. Otherwise
            # I could end up with encrypted content I don't have a key for.
            # NOTE: I always write the config even if it didn't change.
            # Is this less error prone?
            self.config[filename].update(
                dir=post_dir, key=base64.b64encode(key).decode().rstrip('='))
            self.write_config()
            # NOTE: I re-encrypt the content without looking if maybe the output
            # already existed. Re-encrypting may be unnecessary but is hard
            # to avoid since it's hard to determine if any of the content or
            # templates changed, especially with my output being encrypted.
            # Secondly, since image files are stored with new random names, this
            # will leave behind now unused files from previous rounds.
            post.publish(os.path.join(output_dir, post_dir), template_dir, key)


# TODO: unittest this class.
# TODO: add methods to manipulate post sections.
class Post:
    _metadata_pattern = re.compile(
        r'^(?:(?P<key>[a-z0-9_]+): (?P<value>.+)|# .*||(?P<error>.*))$',
        re.MULTILINE)

    # TODO: Require a post to be associated with a Blog? In that case I can set
    # global options on the blog that get used by posts.
    def __init__(self, content=None, title=None):
        self.location = None
        self.title = title
        self._sections = []
        if content:
            self.load(content)

    @classmethod
    def from_file(cls, file_path):
        """Return a new Post from the content in the given `file_path`."""
        with open(file_path, 'rt') as f:
            text = f.read()
        post = cls(text)
        post.location = os.path.dirname(file_path)
        return post

    def load(self, content, override_title=False):
        """Parse string `content` and load it into the Post object.

        If `override_title` is `True` and the metadata in the `content` string
        contains a post title, override the existing title.
        """
        sections = re.split(r'\n\n---\n', content, flags=re.MULTILINE)

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
                parsed_sections.append(section)
        self._sections = parsed_sections
        title = metadata.get('title')
        if title is not None and override_title:
            self.title = title

    @classmethod
    def parse_metadata(cls, content):
        """Parse key-value string and return dict."""
        data = {}
        for match in re.finditer(cls._metadata_pattern, content):
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

    @classmethod
    def dump_metadata(cls, metadata):
        """Return metadata dumped to string in expected content input format."""
        # TODO: Validate metadata?
        return '\n'.join([f'{key}: {value}' for key, value in metadata.items()])

    @classmethod
    def render_commonmark(cls, content):
        """Parse CommonMark and return rendered HTML."""
        parser = commonmark.Parser()
        renderer = HTMLRenderer()
        return renderer.render(parser.parse(content))

    def dump(self):
        """Dump the post back to a mixed CommonMark string."""
        dumped_sections = []
        if self.title:
            dumped_sections.append(f'---\ntitle: {self.title}')
        for section in self._sections:
            if isinstance(section, dict):
                dumped_sections.append(self.dump_metadata(section))
            else:
                dumped_sections.append(section.strip())
        return '\n\n---\n'.join(dumped_sections)

    # TODO: Move encryption elsewhere?
    def publish(self, output_dir, template_dir, key):
        """Write blog post to encrypted files in `output_dir`.

        Render the content using templates from `template_dir`.
        Use `key` bytes as the encryption key.
        `output_dir` will be created if it doesn't exist yet.
        """
        env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=select_autoescape()
        )
        # Normalize path, since the documentation for makedirs says:
        # "makedirs() will become confused if the path elements to create include pardir"
        output_dir = os.path.normpath(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        encrypted_images = {}
        has_panorama = False
        copied_sections = copy.deepcopy(self._sections)
        for section in copied_sections:
            if isinstance(section, dict) and 'image' in section:
                abs_path = os.path.abspath(os.path.join(self.location, section['image']))
                if abs_path not in encrypted_images:
                    img_name = get_random_file_name()
                    encrypted_images[abs_path] = section
                    is_panorama, image_data = get_image_data(abs_path)
                    encrypt(image_data, key, os.path.join(output_dir, img_name))
                    section['image'] = img_name
                    section['is_panorama'] = is_panorama
                    has_panorama = has_panorama or is_panorama
                else:
                    section = encrypted_images[abs_path]
            elif isinstance(section, str):
                section = self.render_commonmark(section)
        content_template = env.get_template('content.html')
        content = content_template.render(content=copied_sections)
        encrypt(content.encode(), key, os.path.join(output_dir, 'content'))
        post_template = env.get_template('post.html')
        with open(os.path.join(output_dir, 'index.html'), 'w') as index_file:
            post = post_template.render(title=self.title, has_panorama=has_panorama)
            index_file.write(post)


def get_random_file_name():
    # Base32 to be compatible with case-insensitive file systems:
    return base64.b32encode(os.urandom(10)).decode().rstrip('=').lower()


def valid_encryption_key(base64key):
    prefix = 'Invalid base64-encoded encryption key:'
    try:
        # Ignore padding. JavaScript's atob() doesn't need it, it looks ugly in
        # URLs and is not always included when e.g. apps turn the copied URL
        # into a clickable link. Too long padding validates.
        base64key = base64key.rstrip('=') + '=='
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
        output_object.write(nonce + aesgcm.encrypt(nonce, data, None))


def get_panorama_data(image):
    for segment, content in image.applist:
        if segment == 'APP1' and b'http://ns.adobe.com/xap/1.0/' in content:
            # Strip out most of the attributes the panorama viewer doesn't need:
            unnecessary_attributes = re.compile(rb"""
                \s*
                (?:xmlns:TPano|TPano:|GPano:(?!Cropped|Full|PoseHeadingDegrees|ProjectionType))
                \w*=".*?"
                """, re.VERBOSE)
            return re.sub(unnecessary_attributes, b'', content)
    return b''


def get_image_data(image_path, max_size=1920):
    """Return a tuple of (is panorama, image data bytes) for a JPEG image.

    Raise a TypeError if `image_path` does not point to a JPEG.

    Resize the image down to fit in a `max_size` square if needed. Don't resize
    the image if it contains GPano XMP data.

    Return a tuple consisting of:
    * a Boolean indicating whether the image has panoramic data,
    * bytes data of the image re-saved as an 80% quality, progressive JPEG
      with all metadata dropped, except for minimal GPano data.
    """
    image = Image.open(image_path)
    if image.format != 'JPEG':
        raise TypeError('Only JPEG images are supported')
    panorama = get_panorama_data(image)
    if not panorama and (image.width > max_size or image.height > max_size):
        image.thumbnail((max_size, max_size))
    tmp = io.BytesIO()
    try:
        image.save(tmp, format='JPEG', quality=80, progressive=True, exif=panorama)
        return (bool(panorama), tmp.getvalue())
    finally:
        tmp.close()


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
