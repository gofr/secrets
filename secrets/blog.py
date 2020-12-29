import base64
import copy
import json
import os
import re
import shutil

import commonmark
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jinja2 import Environment, FileSystemLoader, select_autoescape

from secrets.utils import (
    encrypt, get_image_data, get_random_file_name, decode_encryption_key,
    HTMLRenderer
)


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

    def write(self, output_dir, asset_dir):
        # TODO: Do something less hacky. And allow output dir to exist?
        shutil.copytree(os.path.join(asset_dir, 'static'), output_dir)
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
                key = decode_encryption_key(post_config['key'])
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
            post.publish(os.path.join(output_dir, post_dir), asset_dir, key)


# TODO: unittest this class.
class Post:
    _key_pattern = re.compile(r'[a-z0-9_]+')
    _metadata_pattern = re.compile(
        fr'^(?:(?P<key>{_key_pattern.pattern}): (?P<value>.+)|# .*||(?P<error>.*))$',
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
        if sections[0].startswith('---\n'):
            # Parse the first section, without the leading "---\n":
            metadata = self.parse_metadata(sections.pop(0)[4:])
        for section in sections:
            self.add_section(section)
        title = metadata.get('title')
        if title is not None and override_title:
            self.title = title

    def add_section(self, content):
        """Parse the `content` string and append a single section to the post.

        The string is added as a media section if the first line matches a
        key-value pair. Whitespace-only content is not added.
        """
        match = re.match(self._metadata_pattern, content)
        if match and match.group('key'):
            self._sections.append(self.parse_metadata(content))
        elif content.strip():
            self._sections.append(content)

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
        data = []
        for key, value in metadata.items():
            # This match avoids invalid key strings but also raises an exception
            # if the key is not a string, avoiding potential clashes caused by
            # keys of different types stringifying to the same value.
            if re.fullmatch(cls._key_pattern, key):
                data.append(f'{key}: {value}')
            else:
                raise ValueError(
                    f'Invalid metadata key: "{key}".\n'
                    f'Keys must match regular expression "{cls._key_pattern.pattern}"')
        return '\n'.join(data)

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
    def publish(self, output_dir, asset_dir, key):
        """Write blog post to encrypted files in `output_dir`.

        Render the content using templates from `{asset_dir}/templates`.
        Use `key` bytes as the encryption key.
        `output_dir` will be created if it doesn't exist yet.
        """
        env = Environment(
            loader=FileSystemLoader(os.path.join(asset_dir, 'templates')),
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
