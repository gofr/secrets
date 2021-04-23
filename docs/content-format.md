# Blog content format

Each post consists of a directory with media and CommonMark text files. If a text file has the same name, excluding extension, as a media file it is considered to be a comment on that media file.

The content is displayed in case-insensitive, alphabetical order by file name.

## CommonMark

You can use any CommonMark, however:
* Images are stripped out. Only the [image description](https://spec.commonmark.org/0.29/#image-description) is displayed. You can use CommonMark inside that description.
* Raw HTML is stripped out.

## Media

Only JPEG image files are supported. JPEGs with photo sphere XMP metadata are displayed as interactive panoramas.
