# Blog content format

Each post consists of a single text file with one or more sections separated by text matching the regular expression `/\n\n---\n/`. That is, a blank line followed by a line containing just `---`.

Empty sections are ignored.

Each section can be CommonMark or key-value data used to define post metadata or media content.

## Post metadata ("front matter")

If the first line of the file matches `/^---$/` this marks the start of a blog post metadata section, and the metadata is parsed as [key-value data](#metadata) described below.

## <a id="metadata"></a>Key-value data

The section is considered key-value data if the first line is a key-value pair as defined below. Otherwise it is treated as CommonMark:

* Key-value pairs are lines matching the following regular expression: `/^(?<key>[a-z0-9_]+): (?<value>.+)/`.
* Lines matching `/^# /` are considered comments and are ignored.
* Empty lines, `/^$/`, are ignored.
* Any lines not matching the above patterns raise a ValueError.
* Duplicate keys in the same metadata section raise a ValueError.

### Post metadata keys

Only the first section in a file starting with `/^---$/` is treated as metadata.

<dl>
    <dt><code>title</code></dt>
    <dd>Title to be used in the OpenGraph meta tag and HTML title tag.</dd>
</dl>

### Media keys

<dl>
    <dt><code>image</code></dt>
    <dd>File path to an image.</dd>
</dl>

## CommonMark

You can use any CommonMark, however:
* Images are stripped out. Only the [image description](https://spec.commonmark.org/0.29/#image-description) is displayed. You can use CommonMark inside that description.
* Raw HTML is stripped out.
* Beware that while `---` is valid CommonMark (as a [setext level 2 heading](https://spec.commonmark.org/0.29/#setext-heading-underline) or [thematic break](https://spec.commonmark.org/0.29/#thematic-breaks)), it will first be interpreted as a section separator if it is also preceded by a blank line. Avoid it if possible. Most simply, any occurrence of `/^---$/` can be replaced by `----`.
