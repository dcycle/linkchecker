# -*- coding: iso-8859-1 -*-
# Copyright (C) 2001-2014 Bastian Kleineidam
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
Find link tags in HTML text.
"""

import re
from .. import strformat, log, LOG_CHECK, url as urlutil
from builtins import str as str_text

unquote = strformat.unquote

# HTML4/5 link tags
# ripped mainly from HTML::Tagset.pm with HTML5 added
LinkTags = {
    'a':        [u'href'],
    'applet':   [u'archive', u'src'],
    'area':     [u'href'],
    'audio':    [u'src'],  # HTML5
    'bgsound':  [u'src'],
    'blockquote': [u'cite'],
    'body':     [u'background'],
    'button':   [u'formaction'],  # HTML5
    'del':      [u'cite'],
    'embed':    [u'pluginspage', u'src'],
    'form':     [u'action'],
    'frame':    [u'src', u'longdesc'],
    'head':     [u'profile'],
    'html':     [u'manifest'],  # HTML5
    'iframe':   [u'src', u'longdesc'],
    'ilayer':   [u'background'],
    'img':      [u'src', u'lowsrc', u'longdesc', u'usemap', u'srcset'],
    'input':    [u'src', u'usemap', u'formaction'],
    'ins':      [u'cite'],
    'isindex':  [u'action'],
    'layer':    [u'background', u'src'],
    'link':     [u'href'],
    'meta':     [u'content', u'href'],
    'object':   [u'classid', u'data', u'archive', u'usemap', u'codebase'],
    'q':        [u'cite'],
    'script':   [u'src'],
    'source':   [u'src'],  # HTML5
    'table':    [u'background'],
    'td':       [u'background'],
    'th':       [u'background'],
    'tr':       [u'background'],
    'track':    [u'src'],  # HTML5
    'video':    [u'src'],  # HTML5
    'xmp':      [u'href'],
    None:       [u'style', u'itemtype'],
}

# HTML anchor tags
AnchorTags = {
    'a': [u'name'],
    None: [u'id'],
}

# WML tags
WmlTags = {
    'a':   [u'href'],
    'go':  [u'href'],
    'img': [u'src'],
}


# matcher for <meta http-equiv=refresh> tags
refresh_re = re.compile(r"(?i)^\d+;\s*url=(?P<url>.+)$")

_quoted_pat = r"('[^']+'|\"[^\"]+\"|[^\)\s]+)"
css_url_re = re.compile(r"url\(\s*(?P<url>%s)\s*\)" % _quoted_pat)

# Note that swf_url_re, unlike all other regular expressions here, is meant
# to match byte strings.  Yes, we're scraping binary SWF data for anything
# that looks like a URL.  What did you expect, a full SWF format decoder?
swf_url_re = re.compile(b"(?i)%s" % urlutil.safe_url_pattern.encode('ascii'))

c_comment_re = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_c_comments (text):
    """Remove C/CSS-style comments from text. Note that this method also
    deliberately removes comments inside of strings."""
    return c_comment_re.sub('', text)


def is_meta_url (attr, attrs):
    """Check if the meta attributes contain a URL."""
    res = False
    if attr == "content":
        equiv = attrs.get('http-equiv', u'').lower()
        scheme = attrs.get('scheme', u'').lower()
        res = equiv in (u'refresh',) or scheme in (u'dcterms.uri',)
    if attr == "href":
        rel = attrs.get('rel', u'').lower()
        res = rel in (u'shortcut icon', u'icon')
    return res


def is_form_get(attr, attrs):
    """Check if this is a GET form action URL."""
    res = False
    if attr == "action":
        method = attrs.get('method', u'').lower()
        res = method != 'post'
    return res


class LinkFinder:
    """Find HTML links, and apply them to the callback function with the
    format (url, lineno, column, name, codebase)."""

    def __init__ (self, callback, tags):
        """Store content in buffer and initialize URL list."""
        self.callback = callback
        # set universal tag attributes using tagname None
        self.universal_attrs = set(tags.get(None, []))
        self.tags = dict()
        for tag, attrs in tags.items():
            self.tags[tag] = set(attrs)
            # add universal tag attributes
            self.tags[tag].update(self.universal_attrs)
        self.base_ref = u''

    def html_element (self, tag, attrs, element_text, lineno, column):
        """Search for links and store found URLs in a list."""
        log.debug(LOG_CHECK, "LinkFinder tag %s attrs %s", tag, attrs)
        log.debug(LOG_CHECK, "line %d col %d", lineno, column)
        if tag == "base" and not self.base_ref:
            self.base_ref = attrs.get("href", u'')
        tagattrs = self.tags.get(tag, self.universal_attrs)
        # parse URLs in tag (possibly multiple URLs in CSS styles)
        for attr in sorted(tagattrs.intersection(attrs)):
            if tag == "meta" and not is_meta_url(attr, attrs):
                continue
            if tag == "form" and not is_form_get(attr, attrs):
                continue
            # name of this link
            name = self.get_link_name(tag, attrs, attr, element_text)
            # possible codebase
            base = u''
            if tag == 'applet':
                base = attrs.get('codebase', u'')
            if not base:
                base = self.base_ref
            # note: value can be None
            value = attrs.get(attr)
            if tag == 'link' and attrs.get('rel') == 'dns-prefetch':
                if ':' in value:
                    value = value.split(':', 1)[1]
                value = 'dns:' + value.rstrip('/')
            # parse tag for URLs
            self.parse_tag(tag, attr, value, name, base, lineno, column)
        log.debug(LOG_CHECK, "LinkFinder finished tag %s", tag)

    def get_link_name (self, tag, attrs, attr, name=None):
        """Parse attrs for link name. Return name of link."""
        if tag == 'a' and attr == 'href':
            if not name:
                name = attrs.get('title', u'')
        elif tag == 'img':
            name = attrs.get('alt', u'')
            if not name:
                name = attrs.get('title', u'')
        else:
            name = u""
        return name

    def parse_tag (self, tag, attr, value, name, base, lineno, column):
        """Add given url data to url list."""
        assert isinstance(tag, str_text), repr(tag)
        assert isinstance(attr, str_text), repr(attr)
        assert isinstance(name, str_text), repr(name)
        assert isinstance(base, str_text), repr(base)
        assert isinstance(value, str_text) or value is None, repr(value)
        # look for meta refresh
        if tag == u'meta' and value:
            mo = refresh_re.match(value)
            if mo:
                self.found_url(mo.group("url"), name, base, lineno, column)
            elif attr != 'content':
                self.found_url(value, name, base, lineno, column)
        elif attr == u'style' and value:
            for mo in css_url_re.finditer(value):
                url = unquote(mo.group("url"), matching=True)
                self.found_url(url, name, base, lineno, column)
        elif attr == u'archive':
            for url in value.split(u','):
                self.found_url(url, name, base, lineno, column)
        elif attr == u'srcset':
            for img_candidate in value.split(u','):
                url = img_candidate.split()[0]
                self.found_url(url, name, base, lineno, column)
        else:
            self.found_url(value, name, base, lineno, column)

    def found_url(self, url, name, base, lineno, column):
        """Add newly found URL to queue."""
        assert isinstance(url, str_text) or url is None, repr(url)
        self.callback(url, line=lineno, column=column, name=name, base=base)


def find_links(soup, callback, tags):
    """Parse into content and search for URLs to check.
    When a URL is found it is passed to the supplied callback.
    """
    lf = LinkFinder(callback, tags)
    for element in soup.find_all(True):
        lf.html_element(
            element.name, element.attrs, element.text.strip(),
            element.sourceline,
            None if element.sourcepos is None else element.sourcepos + 1)
