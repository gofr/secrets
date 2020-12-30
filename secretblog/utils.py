import binascii
import base64
import io
import os
import re

import commonmark
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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


def get_random_file_name():
    # Base32 to be compatible with case-insensitive file systems:
    return base64.b32encode(os.urandom(10)).decode().rstrip('=').lower()


def decode_encryption_key(base64key):
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
            raise ValueError(f'{prefix} Key must be 128 bit')
    except binascii.Error as e:
        raise ValueError(f'{prefix} {e}')


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
