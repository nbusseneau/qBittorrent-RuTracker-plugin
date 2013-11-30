# -*- coding: utf-8 -*-
"""rutracker.org search engine plugin for qBittorrent."""
#VERSION: 1.00
#AUTHORS: Skymirrh (skymirrh@skymirrh.net)

import cookielib
import urllib
import urllib2
import tempfile
import os
import sgmllib
import re
import logging

from novaprinter import prettyPrinter

class rutracker(object):
    """rutracker.org search engine plugin for qBittorrent."""
    url = 'http://rutracker.org'
    name = 'rutracker.org'
    login_url = 'http://login.rutracker.org/forum/login.php'
    download_url = 'http://dl.rutracker.org/forum/'
    search_url = 'http://rutracker.org/forum/tracker.php'

    # Your username and password.
    credentials = {'login_username': 'your_username',
                   'login_password': 'your_password',
                   'login': '\xc2\xf5\xee\xe4',}

    def __init__(self):
        """Initialize rutracker search engine, signing in using given credentials."""
        # Initialize cookie handler.
        self.cj = cookielib.CookieJar()
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))
        # Send POST information and sign in.
        logging.info("Trying to connect using given credentials.")
        self.opener.open(self.login_url, urllib.urlencode(self.credentials))
        # Check if connection was successful using cookies.
        if not 'bb_data' in [cookie.name for cookie in self.cj]:
            logging.error("Unable to connect using given credentials.")
            raise ValueError("Unable to connect using given credentials.")
        else:
            logging.info("Connection succesful.")

    def download_torrent(self, url):
        """Download file at url and write it to a file, print the path to the file and the url."""
        # Make temp file.
        file, path = tempfile.mkstemp()
        file = os.fdopen(file, "w")
        # Set up fake bb_dl cookie, needed to trick the server into sending the file.
        id = re.search(r'dl\.php\?t=(\d+)', url).group(1)
        download_cookie = cookielib.Cookie(version=0, name='bb_dl', value=id, port=None, port_specified=False, domain='.rutracker.org', domain_specified=True, domain_initial_dot=True, path='/forum/', path_specified=True, secure=False, expires=None, discard=False, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
        self.cj.set_cookie(download_cookie)
        # Download torrent file at url.
        data = self.opener.open(url).read()
        # Write it to a file.
        file.write(data)
        file.close()
        # Print file path and url.
        print path+" "+url

    class SimpleSGMLParser(sgmllib.SGMLParser):
        """Implement sgmllib.SGMLParser to parse results pages."""
        
        def __init__(self, url, first_page=True):
            """Initialize the parser with url and tell him if he's on the first page of results or not."""
            sgmllib.SGMLParser.__init__(self)
            self.download_url = url
            self.first_page = first_page
            self.results = []
            self.other_pages = []
            self.tr_counter = 0
            self.cat_re = re.compile(r'tracker\.php\?f=\d+')
            self.name_re = re.compile(r'viewtopic\.php\?t=\d+')
            self.link_re = re.compile(r'('+self.download_url+'dl\.php\?t=\d+)')
            self.pages_re = re.compile(r'tracker\.php\?.*?start=(\d+)')
            self.reset_current()

        def reset_current(self):
            """Reset current_item (i.e. torrent) to default values."""
            self.current_item = {'cat': None,
                                 'name': None,
                                 'link': None,
                                 'size': None,
                                 'seeds': None,
                                 'leech': None,}

        def close(self):
            """Override default close() method just to define additional processing."""
            # We add last item found manually because items are added on new
            # <tr class="tCenter"> and not on </tr> (can't do it without the attribute).
            self.results.append(self.current_item)
            sgmllib.SGMLParser.close(self)
            
        def handle_data(self, data):
            """Retrieve inner text information based on rules defined in do_tag()."""
            for key in self.current_item:
                if self.current_item[key] == True:
                    self.current_item[key] = data
                    logging.debug((self.tr_counter, key, data))

        def do_tr(self, attr):
            """<tr class="tCenter"> is the big container for one torrent, so we store current_item and reset it."""
            params = dict(attr)
            try:
                if 'tCenter' in params['class']:
                    # Of course we won't store current_item on first <tr class="tCenter"> seen.
                    if self.tr_counter != 0:
                        # We only store current_item if torrent is still alive.
                        if self.current_item['seeds'] != None:
                            self.results.append(self.current_item)
                        else:
                            self.tr_counter -= 1 # We decrement by one to keep a good value.
                        logging.debug(self.current_item)
                        self.reset_current()
                    self.tr_counter += 1
            except KeyError:
                pass

        def do_a(self, attr):
            """<a> tags can specify torrent link in "href" or category or name in inner text. Also used to retrieve further results pages."""
            params = dict(attr)
            try:
                link = self.link_re.search(params['href'])
                if link:
                    self.current_item['link'] = link.group(0)
                    logging.debug((self.tr_counter, 'link', link.group(0)))
                elif self.cat_re.search(params['href']):
                    self.current_item['cat'] = True
                elif 'data-topic_id' in params and self.name_re.search(params['href']): # data-topic_id is needed to avoid conflicts.
                    self.current_item['name'] = True
                # If we're on the first page of results, we search for other pages.
                elif self.first_page:
                    pages = self.pages_re.search(params['href'])
                    if pages:
                        if pages.group(1) not in self.other_pages:
                            self.other_pages.append(pages.group(1))
            except KeyError:
                pass

        def do_td(self, attr):
            """<td> tags give us number of leechers in inner text and can signal torrent size in next <u> tag."""
            params = dict(attr)
            try:
                if 'tor-size' in params['class']:
                    self.current_item['size'] = False
                elif 'leechmed' in params['class']:
                    self.current_item['leech'] = True
            except KeyError:
                pass

        def do_u(self, attr):
            """<u> tags give us torrent size in inner text."""
            if self.current_item['size'] == False:
                self.current_item['size'] = True

        def do_b(self, attr):
            """<b class="seedmed"> give us number of seeders in inner text."""
            params = dict(attr)
            try:
                if 'seedmed' in params['class']:
                    self.current_item['seeds'] = True
            except KeyError:
                pass

    def parse_search(self, what, start=0, first_page=True):
        """Search for what starting on specified page. Defaults to first page of results."""
        logging.debug("parse_search({}, {}, {})".format(what, start, first_page))
        # Search.
        parser = self.SimpleSGMLParser(self.download_url, first_page)
        page = self.opener.open('{}?nm={}&start={}'.format(self.search_url, urllib.quote(what), start))
        data = page.read().decode('cp1251')
        parser.feed(data)
        parser.close()
        
        # PrettyPrint each torrent found.
        for torrent in parser.results:
            torrent['engine_url'] = self.url
            if __name__ != "__main__": # This is just to avoid printing when I debug.
                prettyPrinter(torrent)

        return (parser.tr_counter, parser.other_pages)

    def search(self, what, cat='all'):
        """Search for what on the search engine."""
        # Search on first page.
        logging.info("Searching for {}...".format(what))
        logging.info("Parsing page 1.")
        (total, pages) = self.parse_search(what)
        logging.info("{} pages of results found.".format(len(pages)+1))

        # Repeat for each page of results.
        for start in pages:
            logging.info("Parsing page {}.".format(int(start)/50+1))
            (counter, _) = self.parse_search(what, start, False)
            total += counter
        
        logging.info("{} torrents found.".format(total))

# For testing purposes.
if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    engine = rutracker()
    engine.search('lazerhawk')
    engine.download_torrent('http://dl.rutracker.org/forum/dl.php?t=4578927')
