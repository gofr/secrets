# Blog content format

Each blog entry consists of a single text file with one or more sections separated by text matching the regular expression `/\n\n---$/`. That is, a blank line followed by a line containing just `---`.

Empty sections are ignored.

Each section can be either simple key-value metadata or CommonMark.

## Metadata

The section is considered metadata if the first line is a key-value pair as defined below. Otherwise it is treated as CommonMark:

* Key-value pairs are lines matching the following regular expression: `/^(?<key>[a-z0-9_]+): (?<value>.+)/`.
* Lines matching `/^# /` are considered comments and are ignored.
* Empty lines, `/^$/`, are ignored.
* Any lines not matching the above patterns raise a ValueError.
* Duplicate keys in the same metadata section raise a ValueError.

### Keys

The following keys are recognized:

<dl>
    <dt>image</dt>
    <dd>File path to an image. If a CommonMark section immediately follows this section it is considered to be a description of or comment on this image.</dd>
</dl>

## CommonMark

You can use any CommonMark, but beware that `---` is also valid CommonMark and will first be interpreted as a section separator if it is also preceded by a blank line. Avoid it if possible. Most simply, any occurrence of `/^---$/` can be replaced by `----`. Alternatively:

* For `---` as a [setext level 2 heading](https://spec.commonmark.org/0.29/#setext-heading-underline), use the [ATX heading syntax](https://spec.commonmark.org/0.29/#atx-heading) or a different number of `-`.
* For `---` as a [thematic break](https://spec.commonmark.org/0.29/#thematic-breaks), use different characters such as `***`, spacing like `- - -`, or a different number of `-`.
