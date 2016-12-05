# -*- coding: utf-8 -*-
"""rutracker.org search engine plugin for qBittorrent."""
#VERSION: 1.05
#AUTHORS: Skymirrh (skymirrh@skymirrh.net)

# Replace YOUR_USERNAME_HERE and YOUR_PASSWORD_HERE with your rutracker.org username and password
credentials = {
    'login_username': u'YOUR_USERNAME_HERE',
    'login_password': u'YOUR_PASSWORD_HERE',
}

# Try blocks are used to circumvent Python2/3 modules discrepancies and use a single script for both versions.
try:
    import cookielib
except ImportError:
    import http.cookiejar as cookielib
    
try:    
    from urllib import urlencode, quote, unquote
    from urllib2 import build_opener, HTTPCookieProcessor, URLError, HTTPError
except ImportError:
    from urllib.parse import urlencode, quote, unquote
    from urllib.request import build_opener, HTTPCookieProcessor
    from urllib.error import URLError, HTTPError

try:
    from HTMLParser import HTMLParser
except ImportError:
    from html.parser import HTMLParser
    
import tempfile
import os
import re
import logging

from novaprinter import prettyPrinter

def dict_encode(dict, encoding='cp1251'):
    """Encode dict values to encoding (default: cp1251)."""
    encoded_dict = {}
    for key in dict:
        encoded_dict[key] = dict[key].encode(encoding)
    return encoded_dict

class rutracker(object):
    """rutracker.org search engine plugin for qBittorrent."""
    url = 'https://rutracker.org'
    name = 'rutracker.org'
    login_url = 'https://rutracker.org/forum/login.php'
    download_url = 'https://rutracker.org/forum/dl.php'
    search_url = 'https://rutracker.org/forum/tracker.php'

    def __init__(self):
        """Initialize rutracker search engine, signing in using given credentials."""
        # Initialize cookie handler.
        self.cj = cookielib.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))
        self.credentials = credentials
        # Add submit button additional POST param.
        self.credentials['login'] = u'Вход'
        # Send POST information and sign in.
        try:
            logging.info("Trying to connect using given credentials.")
            response = self.opener.open(self.login_url, urlencode(dict_encode(self.credentials)).encode())
            # Check if response status is OK.
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(self.login_url, response.getcode()), response.info(), None)
            # Check if login was successful using cookies.
            if not 'bb_data' in [cookie.name for cookie in self.cj]:
                raise ValueError("Unable to connect using given credentials.")
            else:
                logging.info("Login successful.")
        except (URLError, HTTPError, ValueError) as e:
            logging.error(e)

    def download_torrent(self, url):
        """Download file at url and write it to a file, print the path to the file and the url."""
        # Make temp file.
        file, path = tempfile.mkstemp()
        file = os.fdopen(file, "wb")
        # Set up fake POST params, needed to trick the server into sending the file.
        id = re.search(r'dl\.php\?t=(\d+)', url).group(1)
        post_params = {'t': id,}
        # Download torrent file at url.
        try:
            response = self.opener.open(url, urlencode(dict_encode(post_params)).encode())
            # Only continue if response status is OK.
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(self.login_url, response.getcode()), response.info(), None)
        except (URLError, HTTPError) as e:
            logging.error(e)
            return
        # Write it to a file.
        data = response.read()
        file.write(data)
        file.close()
        # Print file path and url.
        print(path+" "+url)

    class Parser(HTMLParser):
        """Implement a simple HTML parser to parse results pages."""
        
        def __init__(self, download_url, first_page=True):
            """Initialize the parser with url and tell him if he's on the first page of results or not."""
            HTMLParser.__init__(self)
            self.download_url = download_url
            self.first_page = first_page
            self.results = []
            self.other_pages = []
            self.tr_counter = 0
            self.cat_re = re.compile(r'tracker\.php\?f=\d+')
            self.name_re = re.compile(r'viewtopic\.php\?t=\d+')
            self.pages_re = re.compile(r'tracker\.php\?.*?start=(\d+)')
            self.reset_current()

        def reset_current(self):
            """Reset current_item (i.e. torrent) to default values."""
            self.current_item = {'cat': None,
                                 'name': None,
                                 'link': None,
                                 'size': None,
                                 'seeds': None,
                                 'leech': None,
                                 'desc_link': None,}

        def close(self):
            """Override default close() method just to define additional processing."""
            # We add last item found manually because items are added on new
            # <tr class="tCenter"> and not on </tr> (can't do it without the attribute).
            self.results.append(self.current_item)
            HTMLParser.close(self)
            
        def handle_data(self, data):
            """Retrieve inner text information based on rules defined in do_tag()."""
            for key in self.current_item:
                if self.current_item[key] == True:
                    self.current_item[key] = data
                    logging.debug((self.tr_counter, key, data))

        def handle_starttag(self, tag, attrs):
            """Pass along tag and attributes to dedicated handlers. Discard any tag without handler."""
            try:
                getattr(self, 'do_{}'.format(tag))(attrs)
            except:
                pass

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
                if self.cat_re.search(params['href']):
                    self.current_item['cat'] = True
                elif 'data-topic_id' in params and self.name_re.search(params['href']): # data-topic_id is needed to avoid conflicts.
                    self.current_item['desc_link'] = 'https://rutracker.org/forum/'+params['href']
                    self.current_item['link'] = 'https://rutracker.org/forum/dl.php?t='+params['data-topic_id']
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
        parser = self.Parser(self.download_url, first_page)
        try:
            response = self.opener.open('{}?nm={}&start={}'.format(self.search_url, quote(what), start))
            # Only continue if response status is OK.
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(self.login_url, response.getcode()), response.info(), None)
        except (URLError, HTTPError) as e:
            logging.error(e)
            return
        
        data = response.read().decode('cp1251')
        parser.feed(data)
        parser.close()
        
        # PrettyPrint each torrent found.
        for torrent in parser.results:
            torrent['engine_url'] = self.url
            if __name__ != "__main__": # This is just to avoid printing when I debug.
                prettyPrinter(torrent)

        # If no torrent were found, stop immediately
        if parser.tr_counter == 0:
            return
            
        # Else return number of torrents found
        return (parser.tr_counter, parser.other_pages)

    def search(self, what, cat='all'):
        """Search for what on the search engine."""
        # Search on first page.
        what = unquote(what)
        logging.info("Searching for {}...".format(what))
        logging.info("Parsing page 1.")
        results = self.parse_search(what)
        
        # If no results, stop
        if results == None:
            return
            
        # Else return current count (total) and all pages found
        (total, pages) = results
        logging.info("{} pages of results found.".format(len(pages)+1))

        # Repeat search for each page of results.
        for start in pages:
            logging.info("Parsing page {}.".format(int(start)/50+1))
            results = self.parse_search(what, start, False)
            if results != None:
                (counter, _) = results
                total += counter
        
        logging.info("{} torrents found.".format(total))

# For testing purposes.
if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    engine = rutracker()
    engine.search('lazerhawk')
    engine.download_torrent('https://rutracker.org/forum/dl.php?t=4578927')
