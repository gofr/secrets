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
    <dt>title</dt>
    <dd>Title to be used in the OpenGraph meta tag and HTML title tag.</dd>
</dl>

### Media keys

<dl>
    <dt>image</dt>
    <dd>File path to an image.</dd>
</dl>

## CommonMark

You can use any CommonMark, but beware that `---` is also valid CommonMark and will first be interpreted as a section separator if it is also preceded by a blank line. Avoid it if possible. Most simply, any occurrence of `/^---$/` can be replaced by `----`. Alternatively:

* For `---` as a [setext level 2 heading](https://spec.commonmark.org/0.29/#setext-heading-underline), use the [ATX heading syntax](https://spec.commonmark.org/0.29/#atx-heading) or a different number of `-`.
* For `---` as a [thematic break](https://spec.commonmark.org/0.29/#thematic-breaks), use different characters such as `***`, spacing like `- - -`, or a different number of `-`.
