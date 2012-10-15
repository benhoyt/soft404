Soft 404 (dead page) detector in Python
=======================================

*I'm putting this here mainly for historical interest. I haven't used this in
a long time, and it may be suffering from bit rot, but the algorithm is
interesting.*

This algorithm was taken from the paper *Sic Transit Gloria Telae: Towards an
Understanding of the Web's Decay* by Tomkins et al (which is, somewhat
ironically, a dead page):

http://www.tomkinshome.com/andrew/papers/decay/final/p444-baryossef.htm

I needed a way for [DecentURL.com](http://decenturl.com/)'s "link rot
detector" to properly detect dead pages. It'd be nice if all web servers
returned real 404s, but they don't. Some websites (youtube.com, stuff.co.nz)
return the home page, or redirect you somewhere, making it difficult for a
program to tell whether a link is dead or not. The paper calls these pages
"soft 404s", and they're non-trivial to detect.

Basically, you fetch the URL in question. If you get a hard 404, it's easy:
the page is dead. But if it returns 200 OK with a page, then we don't know if
it's a good page or a soft 404. So we fetch a known bad URL (the parent
directory of the original URL plus some random chars). If that returns a hard
404 then we know the host returns hard 404s on errors, and since the original
page fetched okay, we know it must be good.

But if the known dead URL returns a 200 OK as well, we know it's a host which
gives out soft 404s. So then we need to test the contents of the two pages. If
the content of the original URL is (almost) identical to the content of the
known bad page, the original must be a dead page too. Otherwise, if the
content of the original URL is different, it must be a good page.

That's the heart of it. The redirects complicate things just slightly, but not
much. For more info, see section 3 in the paper referred to above.

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

See my [original blog entry](http://blog.brush.co.nz/2008/01/soft404s/) for
further context.
