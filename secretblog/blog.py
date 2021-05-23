from abc import ABC, abstractmethod
import collections
import json
import os
import shutil
import subprocess

import commonmark
from geojson import MultiLineString
from PIL import Image

from secretblog.gpx import GPXParser
from secretblog.utils import (
    Cipher, HTMLRenderer, JSONConfigDecoder, JSONConfigEncoder, find_in_file, get_image_data,
    get_random_file_name
)


class Blog:
    CONFIG_NAME = "secrets.json"  # Name of file in the input_dir

    def __init__(self, input_dir, output_dir, asset_dir):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.asset_dir = asset_dir
        self.config = self.load_config()
        posts = {}
        for entry in os.scandir(input_dir):
            if entry.is_dir():
                posts[entry.name] = Post(self, entry.path)
        self.posts = posts

    def load_config(self):
        try:
            config = {"posts": {}}
            with open(os.path.join(self.input_dir, self.CONFIG_NAME)) as f:
                config.update(json.load(f, cls=JSONConfigDecoder))
        except FileNotFoundError:
            pass
        return config

    def write_config(self):
        # NOTE: It's quite important not to lose the config since it holds
        # encryption keys. This is reasonably safe now, but not thread-safe.
        config_file = os.path.join(self.input_dir, self.CONFIG_NAME)
        # Dump to string to find errors early and not end up with a corrupt file:
        config = json.dumps(self.config, cls=JSONConfigEncoder, indent=4)
        try:
            # Move the old config out of the way, replacing the old backup.
            os.replace(config_file, config_file + ".bak")
        except FileNotFoundError:
            pass  # There was nothing to move.
        # Now write the new file:
        with open(config_file, "x") as f:
            f.write(config)

    def write(self):
        self.copy_assets()
        # Update the config before writing the encrypted files. Otherwise
        # I could end up with encrypted content I don't have a key for.
        self.write_config()
        for post in self.posts.values():
            # NOTE: I re-encrypt the content without looking if maybe the output
            # already existed. Re-encrypting may be unnecessary but is hard
            # to avoid since it's hard to determine if any of the content
            # changed, especially with my output being encrypted.
            # Secondly, since image files are stored with new random names, this
            # will leave behind now unused files from previous rounds.
            post.render()

    def copy_assets(self):
        # TODO: Do something less hacky. And allow output dir to exist?
        subprocess.run(["npm", "run", "build"], cwd=self.asset_dir, check=True)
        shutil.copytree(os.path.join(self.asset_dir, "dist"), self.output_dir)
        shutil.copytree(
            os.path.join(self.asset_dir, "static"), self.output_dir, dirs_exist_ok=True)


# NOTE: I can't create posts programmatically now. Content is always read from files.
# Is that a problem?
class Post:
    def __init__(self, blog, path):
        self.blog = blog
        self.path = path
        self.config = blog.config["posts"].setdefault(os.path.basename(path), {})
        self.config.setdefault("key", Cipher())
        self.config.setdefault("dir", get_random_file_name())
        content = {}
        for entry in os.scandir(path):
            if not entry.is_file():
                continue
            root, ext = os.path.splitext(entry.name)
            lower_root, lower_ext = os.path.splitext(entry.name.lower())
            if lower_ext not in PostComponent.REGISTERED_TYPES:
                print(f"Unrecognized file type ({ext}) ignored: {entry.path}")
                continue
            item = PostSection(self, entry.path)
            sort_key = (lower_root, root)
            if sort_key in content:
                content[sort_key].add(item)
            else:
                content[sort_key] = item
        self.content = [v for k, v in sorted(content.items())]

    def render(self):
        # Normalize path, since the documentation for makedirs says:
        # "makedirs() will become confused if the path elements to create include pardir"
        output_dir = os.path.normpath(os.path.join(self.blog.output_dir, self.config["dir"]))
        os.makedirs(output_dir, exist_ok=True)
        content = "".join([section.render() for section in self.content])
        self.config["key"].encrypt(content.encode(), os.path.join(output_dir, "content"))
        # TODO: I don't have any variables in this "template" anymore. Unless I
        # bring back the title or so, I don't need Jinja, and I don't need this
        # to be a template. I shouldn't even need this to exist separately for
        # each post. I could just have a single index.html in the root which
        # takes the post dir as a search or hash argument.
        # If I'm going to bring back a title, it would be better to have it
        # encrypted too anyway, which means it's not going to be hard-coded in
        # the HTML but injected from JavaScript.
        shutil.copy(
            os.path.join(self.blog.asset_dir, "templates", "post.html"),
            os.path.join(output_dir, "index.html")
        )


class PostSection:
    __slots__ = ["post", "media", "text"]

    def __init__(self, post, item1, item2=None, /):
        self.post = post
        component1 = PostComponent.load(post, item1)
        component2 = None
        if item2 is not None:
            component2 = PostComponent.load(post, item2)
            if component2 and component1.is_text() == component2.is_text():
                raise ValueError(
                    f'"{item2}" must have a different content type (text or media) than "{item1}"')
        if component1.is_text():
            self.text = component1
            self.media = component2
        else:
            self.text = component2
            self.media = component1

    def add(self, other):
        if (self.media and not other.media) and (other.text and not self.text):
            self.text = other.text
        elif (self.text and not other.text) and (other.media and not self.media):
            self.media = other.media
        else:
            raise ValueError("Too many items to combine into a single section")

    def render(self):
        media = self.media.render() if self.media else ""
        text = self.text.render() if self.text else ""
        return f"<section>{media}{text}</section>"


class PostComponent(ABC):
    EXTENSIONS = None
    REGISTERED_TYPES = collections.defaultdict(list)

    def __init__(self, post, path):
        self.post = post
        self.path = path

    @classmethod
    def register(cls, class_):
        for ext in class_.EXTENSIONS:
            cls.REGISTERED_TYPES[ext].append(class_)

    @classmethod
    def load(cls, post, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in cls.REGISTERED_TYPES:
            for class_ in reversed(cls.REGISTERED_TYPES[ext]):
                try:
                    return class_(post, path)
                except TypeError:
                    pass
            else:
                raise ValueError(f"No registered handlers could handle {path}.")
        else:
            raise TypeError(f"There is no registered handler for {ext} files.")

    def is_text(self):
        return isinstance(self, TextComponent)

    @abstractmethod
    def render(self):
        pass


class TextComponent(PostComponent):
    pass


class MediaComponent(PostComponent):
    pass


class CommonMarkComponent(TextComponent):
    EXTENSIONS = ('.md',)

    def render(self):
        with open(self.path, "rt") as f:
            content = f.read()
        parser = commonmark.Parser()
        renderer = HTMLRenderer()
        html = renderer.render(parser.parse(content))
        return f'<div class="content">{html}</div>'


class ImageComponent(MediaComponent):
    EXTENSIONS = ('.jpeg', '.jpg', '.png')

    def save(self):
        name = get_random_file_name()
        image_data = get_image_data(Image.open(self.path))
        output = os.path.join(self.post.blog.output_dir, self.post.config["dir"], name)
        self.post.config["key"].encrypt(image_data, output)
        return name

    def render(self):
        img = self.save()
        return f'<div class="media"><img data-src="{img}"></div>'


# TODO: Don't use a separate class for this, but let ImageComponent
# return different HTML if the image contained GPano metadata?
class PanoramaComponent(ImageComponent):
    def __init__(self, post, path):
        # Needle size affects search speed. Search for a somewhat long string
        # that must exist in photo sphere XMP metadata:
        if find_in_file(path, b"GPano:CroppedAreaImageHeightPixels"):
            return super().__init__(post, path)
        else:
            raise TypeError("Image is not a panorama. No GPano XMP tags found.")

    def render(self):
        img = self.save()
        return f'<div class="media"><div class="panorama" data-panorama="{img}"></div></div>'


# TODO: OOP-ify the JavaScript side too, so that's as easily extendable.
class MapComponent(MediaComponent):
    EXTENSIONS = ('.gpx',)

    def get_geojson(self):
        """Parse GPX `self.path` and return GeoJSON string."""
        with open(self.path) as f:
            gpx = GPXParser(f).parse()
        return str(MultiLineString(gpx.get_polylines())).encode()

    # TODO: If the GPX has waypoints that reference images which exist in the
    # Post object, include the waypoints in the GeoJSON and mark them on the map.
    # Clicking on one scrolls to the image. And the image gets an overlay icon
    # you can click to go back to the map, with the waypoint highlighted.
    # TODO: Don't use a live OpenStreetMap. Download all the tiles and store
    # them locally, encrypted and the name hashed so the location is obscured.
    def save(self):
        name = get_random_file_name()
        output = os.path.join(self.post.blog.output_dir, self.post.config["dir"], name)
        self.post.config["key"].encrypt(self.get_geojson(), output)
        return name

    def render(self):
        geojson = self.save()
        return f'<div class="media"><div class="map" data-geojson="{geojson}"></div></div>'


PostComponent.register(CommonMarkComponent)
PostComponent.register(ImageComponent)
PostComponent.register(PanoramaComponent)
PostComponent.register(MapComponent)
