"""Soft 404 (dead page) detector by Ben Hoyt

Use this as you please, but let me (benhoyt.com) know if you like it,
or if you find bugs or issues with it.

This algorithm was taken from the paper "Sic Transit Gloria Telae:
Towards an Understanding of the Web's Decay" by Tomkins et al:

http://www.tomkinshome.com/andrew/papers/decay/final/p444-baryossef.htm

History: I needed a way for DecentURL.com's "link rot detector" to
properly detect dead pages. It'd be nice if all web servers returned
real 404s, but they don't. Some websites (youtube.com, stuff.co.nz)
return the home page, or redirect you somewhere, making it difficult
for a program to tell whether a link is dead or not. The paper calls
these pages "soft 404s", and they're non-trivial to detect.

Basically, you fetch the URL in question. If you get a hard 404, it's
easy: the page is dead. But if it returns 200 OK with a page, then we
don't know if it's a good page or a soft 404. So we fetch a known bad URL
(the parent directory of the original URL plus some random chars). If
that returns a hard 404 then we know the host returns hard 404s on errors,
and since the original page fetched okay, we know it must be good.

But if the known dead URL returns a 200 OK as well, we know it's a host
which gives out soft 404s. So then we need to test the contents of the
two pages. If the content of the original URL is (almost) identical to
the content of the known bad page, the original must be a dead page too.
Otherwise, if the content of the original URL is different, it must be a
good page.

That's the heart of it. The redirects complicate things just slightly,
but not much. For more info, see the above paper online, section 3.

To use this soft 404 detector, just type something like:

>>> is_dead('http://micropledge.com/asflkjdasfkljdsfa')
True
>>> is_dead('http://stuff.co.nz/asflkjdasfkljdsfa')
True
>>> is_dead('http://stuff.co.nz/4344033a10.html')
False
>>> is_dead('http://micropledge.com/')
False
>>> is_dead('http://decenturl.com/premium')
False

Or call it from the command line like:

> python soft404.py http://micropledge.com/
alive: http://micropledge.com/
> python soft404.py http://micropledge.com/asflkjdasfkljdsfa
dead: http://micropledge.com/asflkjdasfkljdsfa
"""

import difflib
import httplib
import random
import socket
import string
import urllib2
import urlparse

TIMEOUT = 10
MAX_READ = 64*1024
MAX_REDIRECTS = 10
IDENTICAL_RATIO = 0.95
RANDOM_LETTERS = 25

def almost_identical(html1, html2, minratio=IDENTICAL_RATIO):
    """Return True if html1 and html2 web pages are almost identical, i.e.,
    at least minratio*100 percent the same. The documents are first split
    on whitespace boundaries (rather than lines) because some HTML pages
    hardly use any line breaks, so it should give a better comparison than
    a line-by-line diff.

    >>> h1 = 'a b c d e f g h i j k l m n o p q r s t u v w x y z'
    >>> h2 = 'a b c d e f g h i j k l m n o p q r s t u v w x y z'
    >>> almost_identical(h1, h2)
    True
    >>> h2 = 'a b c d e f g h i j k l m n o p q r s t u v w y z'
    >>> almost_identical(h1, h2)
    True
    >>> h2 = 'a b c d e f g h i j k l m n o p q r s t u v z'
    >>> almost_identical(h1, h2)
    False
    >>> h2 = 'z y x w v u t s r q p o n m l k j i h g f e d c b a'
    >>> almost_identical(h1, h2)
    False
    """
    seq1 = html1.split()
    seq2 = html2.split()
    sm = difflib.SequenceMatcher(None, seq1, seq2)
    return sm.ratio() >= minratio

def random_letters(n):
    """Return a string of n random lowercase letters.

    >>> r1 = random_letters(25)
    >>> r2 = random_letters(25)
    >>> len(r1) == len(r2)
    True
    >>> r1 == r2
    False
    """
    letter_list = [random.choice(string.ascii_lowercase) for i in range(n)]
    return ''.join(letter_list)

def get_parent(url):
    """Return the URL's parent path (returned path ends with slash).

    >>> get_parent('http://site.com')
    'http://site.com/'
    >>> get_parent('http://site.com/')
    'http://site.com/'
    >>> get_parent('http://site.com/one')
    'http://site.com/'
    >>> get_parent('http://site.com/one/')
    'http://site.com/'
    >>> get_parent('http://site.com/one/two')
    'http://site.com/one/'
    >>> get_parent('http://site.com/one/two/')
    'http://site.com/one/'
    """
    scheme, host, path = urlparse.urlparse(url)[:3]
    if path.endswith('/'):
        path = path[:-1]
    parent_path = '/'.join(path.split('/')[:-1])
    return scheme + '://' + host + parent_path + '/'

def get_path(url):
    """Return just the path portion of a URL, or '/' if none.

    >>> get_path('http://site.com')
    '/'
    >>> get_path('http://site.com/')
    '/'
    >>> get_path('http://site.com/path/to/page/')
    '/path/to/page/'
    """
    scheme, host, path = urlparse.urlparse(url)[:3]
    if path == '':
        path = '/'
    return path

class Redirect(Exception):
    """Raised by our NoRedirects() handler to signal a redirect."""
    def __init__(self, code, newurl, fp):
        self.code = code
        self.newurl = newurl
        self.fp = fp

class NoRedirects(urllib2.HTTPRedirectHandler):
    """Redirect handler that simply raises a Redirect()."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Redirect(code, newurl, fp)

def atomic_fetch(url):
    """Try to get a page without following redirects. Return tuple
    (html, newurl), where html is the HTML if a good page was fetched or
    None on error, and newurl is the new location if it's a redirect or
    None if not.
    """
    opener = urllib2.build_opener(NoRedirects())
    try:
        fp = opener.open(url)
        html = fp.read(MAX_READ)
        return (html, None)      # normal page (code 200)
    except Redirect, e:
        html = e.fp.read(MAX_READ)
        return (html, e.newurl)  # redirect (code 3xx)
    except (urllib2.URLError, httplib.HTTPException, \
            socket.timeout, ValueError), e:
        return (None, None)      # page not found (4xx, 5xx, or other error)

def fetch(url):
    """Returns (html, final, n), where html is the HTML if a normal page
    was fetched or None on error, final is the final URL if it was a good
    page, and n is the number of redirects in any case. Also returns error
    (html is None) on too many redirects or if a redirect loop is detected.
    """
    n = 0
    fetched = {}
    while True:
        fetched[url] = True
        html, newurl = atomic_fetch(url)
        if html is None:
            return (None, None, n)  # hard 404 (or other error)
        if newurl is None:
            return (html, url, n)   # got a normal page, all good
        if newurl in fetched:
            return (None, None, n)  # a redirect loop
        if n >= MAX_REDIRECTS:
            return (None, None, n)  # too many redirects
        url = newurl
        n += 1

def _is_dead(url):
    """This is the heart of the algorithm. But use is_dead() instead of
    this -- this function exists only so we can have is_dead() save and
    restore the default socket timeout.
    """
    html, final, n = fetch(url)
    if html is None:
        return True   # hard 404 (or other error)
    # rand_url is a known dead page to compare against
    rand_url = get_parent(url) + random_letters(RANDOM_LETTERS)
    rand_html, rand_final, rand_n = fetch(rand_url)
    if rand_html is None:
        return False  # host returns a hard 404 on dead pages
    if get_path(url) == '/':
        return False  # a root can't be a soft 404
    if n != rand_n:
        return False  # different number of redirects
    if final == rand_final:
        return True   # same redirect (and same # of redirects)
    if almost_identical(html, rand_html):
        return True   # original url almost identical to "error page"
    return False      # not a soft 404

def is_dead(url):
    """Return True if url looks like a dead page, otherwise False."""
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(TIMEOUT)
    r = _is_dead(url)
    socket.setdefaulttimeout(old_timeout)
    return r

def main():
    import sys
    if len(sys.argv) < 2:
        print 'Soft 404 (dead page) detector by Ben Hoyt'
        print 'Usage: soft404.py url|test'
        sys.exit(2)
    url = sys.argv[1]
    if url == 'test':
        import doctest
        doctest.testmod()
        sys.exit(0)
    if is_dead(url):
        print 'dead:', url
        sys.exit(1)
    else:
        print 'alive:', url
        sys.exit(0)

if __name__ == '__main__':
    main()
