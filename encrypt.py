#!/usr/bin/env python3

import argparse
import textwrap

from secretblog.blog import Blog


def publish(input_dir, output_dir, asset_dir):
    blog = Blog(input_dir, output_dir, asset_dir)
    blog.write()


if __name__ == "__main__":
    class RawDescriptionAndDefaultsHelpFormatter(
            argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(
        formatter_class=RawDescriptionAndDefaultsHelpFormatter,
        description=textwrap.dedent("""\
        Create a secret, encrypted blog

        This tool treats each sub-directory inside the specified input directory
        as a blog post. The contents of each sub-directory are read according to
        content-format.md and its contents are encrypted and saved to a
        randomly-named subfolder inside the specified output directory.

        A file called secrets.json is created (or updated) inside the input
        directory that maps the original sub-directory name to the name of its
        output directory and the encryption key that was used. Each post is
        encrypted with a different key. All content of one post uses the same
        key but a different IV.

        The resulting output can be hosted anywhere that supports static content
        and HTTPS. To load the decrypted content, use the encryption key as the
        hash. E.g. https://your.host/randomdirname/#theencryptionkey

        The key is not sent to the server in this way, but this is clearly not
        very secure for at least two reasons:
        * Anyone you share a link with will have the encryption key and can
          decrypt the content you shared with them. They might accidentally or
          deliberately share that link with others. For example, it may be
          exposed in their browser history.
        * This method is not host-proof. For example, it would be possible for
          a malicious host to inject JavaScript that retrieves the encryption
          key even if it isn't normally sent to them.

        The decryption happens on the client side using the Web Crypto API:
        https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API

        As that documentation states:

        "If you're not sure you know what you are doing, you probably shouldn't
        be using this API."

        I don't know what I'm doing. Don't use this tool for anything serious.
        """))
    parser.add_argument("input_dir", help="path to directory with blog content")
    parser.add_argument("output_dir", help="path to directory to write encrypted content to")
    parser.add_argument(
        "--asset-dir", default="assets",
        help="""\
            path to directory containing public assets. This should include at
            least three sub-directories: src/, static/ and templates/. The src/
            directory contains resources that will be processed by webpack
            to generate minified JS that is then copied to the output directory.
            The static/ directory contains other resources that are needed to
            display the site. These are copied to the output directory unchanged.
            The templates/ directory contains Jinja files used to generate the content.
            """)

    args = parser.parse_args()
    publish(args.input_dir, args.output_dir, args.asset_dir)
