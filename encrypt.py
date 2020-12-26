#!/usr/bin/env python3

import argparse
import textwrap

from blog import Blog


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
