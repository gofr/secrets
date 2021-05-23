import base64
import binascii
import io
import json
import os
import re

import commonmark
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


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
        options.setdefault("safe", True)
        super().__init__(options)

    def tag(self, name, attrs=None, selfclosing=None):
        # Self-closing tags don't exist in HTML:
        super().tag(name, attrs, False)

    def image(self, node, entering):
        # Don't render the image at all in safe mode, only the alt text,
        # but allow tags in that text in that case.
        if not self.options.get("safe"):
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
        if not self.options.get("safe"):
            super().html_inline(node, entering)

    def html_block(self, node, entering):
        if not self.options.get("safe"):
            super().html_block(node, entering)


class JSONConfigDecoder(json.JSONDecoder):
    def __init__(self, **kwargs):
        kwargs["object_hook"] = self._object_hook
        super().__init__(**kwargs)

    def _object_hook(self, o):
        if "key" in o:
            o["key"] = Cipher(o["key"])
        return o

    def decode(self, s):
        o = super().decode(s)
        o.setdefault("posts", {})
        return o


class JSONConfigEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Cipher):
            return str(o)
        else:
            return super().default(o)


class Cipher:
    """AES-GCM encryption cipher"""
    def __init__(self, key=None):
        bits = 256
        prefix = "Invalid encryption key:"
        if key is None:
            self.key = AESGCM.generate_key(bit_length=bits)
        else:
            try:
                # Ignore padding. JavaScript's atob() doesn't need it, it looks ugly in
                # URLs and is not always included when e.g. apps turn the copied URL
                # into a clickable link. Too long padding validates.
                key = key.rstrip("=") + "=="
                # Use altchars arg instead of urlsafe_b64decode() because the
                # latter doesn't take a validate arg.
                key = base64.b64decode(key, altchars='-_', validate=True)
            except TypeError:
                # .rstrip() failed. The key is probably bytes-like. Use it directly.
                pass
            except (AttributeError, binascii.Error) as e:
                raise ValueError(f"{prefix} {e}") from None
            if len(key) == bits // 8:
                self.key = key
            else:
                raise ValueError(f"{prefix} Key must be {bits} bits")
        self.cipher = AESGCM(self.key)

    def __str__(self):
        """Return the base64-encoded encryption key."""
        return base64.urlsafe_b64encode(self.key).decode().rstrip("=")

    def encrypt(self, data, output_file):
        """Encrypt and write `data` bytes to `output_file`."""
        nonce = os.urandom(12)  # 96 random bits
        with open(output_file, "wb") as f:
            f.write(nonce + self.cipher.encrypt(nonce, data, None))


def get_random_file_name():
    # Base32 to be compatible with case-insensitive file systems:
    return base64.b32encode(os.urandom(10)).decode().rstrip("=").lower()


def find_in_file(path, needle):
    """Return True if bytes `needle` are in binary file `path`."""
    # All possible partial matches at the end of a read chunk:
    ends = tuple(needle[0:-i] for i in range(1, len(needle)))
    with open(path, "rb") as f:
        previous = None
        while data := f.read(128 * 1024):
            if previous:
                data = b"".join([previous, data])
            if needle in data:
                return True
            previous = data[-len(needle):] if data.endswith(ends) else None
        return False


# TODO: Add support for getting XMP data from GIF and WebP?
# https://www.adobe.com/content/dam/acom/en/devnet/xmp/pdfs/XMPSDKReleasecc-2020/XMPSpecificationPart3.pdf
# https://developers.google.com/speed/webp/docs/riff_container
def get_panorama_data(image):
    """Return JPEG-formatted XMP data containing the `image` panorama metadata."""
    xmp_header = b"http://ns.adobe.com/xap/1.0/"
    unnecessary_xml = re.compile(rb"""
        \s+
        # Match all attributes that aren't related to panorama data
        (?:xmlns:(?!(?:x|rdf|GPano)\b)|(?!xmlns:|GPano:)[\w:]+|GPano:(?!Cropped|Full|PoseHeadingDegrees|ProjectionType))
        \w*=".*?"
        |
        # And match all tags that aren't related to panorama data
        \s*<(?!/?x:|/?rdf:(?:RDF|Description))[^>]*>\s*
        """, re.VERBOSE)
    # JPEG
    if hasattr(image, "applist"):
        for segment, content in image.applist:
            if segment == "APP1" and xmp_header in content and b"GPano" in content:
                return re.sub(unnecessary_xml, b"", content)
    # PNG
    elif hasattr(image, "info"):
        content = image.info.get("XML:com.adobe.xmp")
        if content and "GPano" in content:
            return b"\x00".join([xmp_header, re.sub(unnecessary_xml, b"", content.encode())])
    return b""


def get_image_data(image, max_size=1920):
    """Return image data bytes as an 80% quality, progressive JPEG.

    Raise a TypeError if `image` is not a JPEG or PNG Image object.

    Resize the image down to fit in a `max_size` square if needed. Don't resize
    the image if it contains GPano XMP metadata. Don't save any other metadata.
    """
    if image.format not in ("JPEG", "PNG"):
        raise TypeError("Only JPEG and PNG images are supported")
    panorama = get_panorama_data(image)
    if image.mode != "RGB":
        image = image.convert("RGB")
    if not panorama:
        image.thumbnail((max_size, max_size))
    tmp = io.BytesIO()
    try:
        image.save(tmp, format="JPEG", quality=80, progressive=True, exif=panorama)
        return tmp.getvalue()
    finally:
        tmp.close()
