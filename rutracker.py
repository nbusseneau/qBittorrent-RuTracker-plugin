# -*- coding: utf-8 -*-
"""RuTracker search engine plugin for qBittorrent."""
#VERSION: 1.13
#AUTHORS: Skymirrh (skymirrh@gmail.com)

# Replace YOUR_USERNAME_HERE and YOUR_PASSWORD_HERE with your RuTracker username and password
credentials = {
    'login_username': u'YOUR_USERNAME_HERE',
    'login_password': u'YOUR_PASSWORD_HERE',
}

# List of RuTracker mirrors
mirrors = [
    'https://rutracker.org',
    'https://rutracker.net',
    'https://rutracker.nl',
    'https://rutracker.cr',
]

# Logging
import logging
logger = logging.getLogger()
logger.setLevel(logging.WARNING)

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

from novaprinter import prettyPrinter

def dict_encode(dict, encoding='cp1251'):
    """Encode dict values to encoding (default: cp1251)."""
    encoded_dict = {}
    for key in dict:
        encoded_dict[key] = dict[key].encode(encoding)
    return encoded_dict

class rutracker(object):
    """RuTracker search engine plugin for qBittorrent."""
    name = 'RuTracker'
    url = 'https://rutracker.org' # We MUST produce an URL attribute at instantiation time, otherwise qBittorrent will fail to register the engine, see #15
    
    @property
    def forum_url(self):
        return self.url + '/forum'
        
    @property
    def login_url(self):
        return self.forum_url + '/login.php'
        
    @property
    def download_url(self):
        return self.forum_url + '/dl.php'
        
    @property
    def search_url(self):
        return self.forum_url + '/tracker.php'

    def __init__(self):
        """Initialize RuTracker search engine, signing in using given credentials."""
        # Initialize various objects.
        self.cj = cookielib.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))
        self.url = self.initialize_url() # Override url with the actual URL to be used (in case official URL isn't accessible)
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
            if not 'bb_session' in [cookie.name for cookie in self.cj]:
                logging.debug(self.cj)
                raise ValueError("Unable to connect using given credentials.")
            else:
                logging.info("Login successful.")
        except (URLError, HTTPError, ValueError) as e:
            logging.error(e)

    def initialize_url(self):
        """Try to find a reachable RuTracker mirror."""
        for mirror in mirrors:
            try:
                self.opener.open(mirror)
                logging.info("Found reachable mirror: {}".format(mirror))
                return mirror
            except URLError:
                pass
        logging.error("Unable to resolve any RuTracker mirror.")
        return ''
    
    def download_torrent(self, url):
        """Download file at url and write it to a file, print the path to the file and the url."""
        # Make temp file.
        file, path = tempfile.mkstemp('.torrent')
        file = os.fdopen(file, "wb")
        # Set up fake POST params, needed to trick the server into sending the file.
        id = re.search(r'dl\.php\?t=(\d+)', url).group(1)
        post_params = {'t': id,}
        # Download torrent file at url.
        try:
            response = self.opener.open(url, urlencode(dict_encode(post_params)).encode())
            # Only continue if response status is OK.
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(url, response.getcode()), response.info(), None)
        except (URLError, HTTPError) as e:
            logging.error(e)
            raise e
        # Write it to a file.
        data = response.read()
        file.write(data)
        file.close()
        # Print file path and url.
        print(path+" "+url)

    class Parser(HTMLParser):
        """Implement a simple HTML parser to parse results pages."""
        
        def __init__(self, engine):
            """Initialize the parser with url and tell him if he's on the first page of results or not."""
            # In Python 3 convert_charrefs is set to True by default: handle_data() receives HTML entities as regular data, handle_entityref() does nothing.
            # In Python 2 there is no convert_charrefs: HTML entities are always processed by handle_entityref().
            # Thus, we make Python 3 work like Python 2 in order to standardize HTML entities handling.
            try:
                HTMLParser.__init__(self, convert_charrefs=False)
            except:
                HTMLParser.__init__(self)
            self.engine = engine
            self.results = []
            self.other_pages = []
            self.tr_counter = 0
            self.cat_re = re.compile(r'tracker\.php\?f=\d+')
            self.name_re = re.compile(r'viewtopic\.php\?t=\d+')
            self.pages_re = re.compile(r'tracker\.php\?.*?start=(\d+)')
            self.size_re = re.compile(r'[^.0-9a-zA-Z]+')
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

        def handle_data(self, data):
            """Retrieve inner text information based on rules defined in do_tag()."""
            for key in self.current_item:
                if self.current_item[key] == True:
                    if key == 'size':
                        self.current_item['size'] = self.size_re.sub(r'', data)
                    elif key == 'size_extension':
                        self.current_item['size'] += data
                    else:
                        self.current_item[key] = data
                    logging.debug('handle_data: ' + str((self.tr_counter, key, data)))
            if 'size_extension' in self.current_item:
                del self.current_item['size_extension']

        def handle_entityref(self, entity):
            """When encountering a &nbsp; after setting size, this means next handle_data() will received size extension (e.g. 'MB', 'GB')"""
            if entity == "nbsp" and self.current_item['size'] is not None:
                self.current_item['size_extension'] = True

        def handle_starttag(self, tag, attrs):
            """Pass along tag and attributes to dedicated handlers. Discard any tag without handler."""
            try:
                getattr(self, 'do_{}'.format(tag))(attrs)
            except:
                pass
                
        def handle_endtag(self, tag):
            """Add last item manually on html end tag."""
            # We add last item found manually because items are added on new
            # <tr class="tCenter"> and not on </tr> (can't do it without the attribute).
            if tag == 'html' and self.current_item['seeds'] != None:
                self.results.append(self.current_item)

        def do_tr(self, attr):
            """<tr class="tCenter"> is the big container for one torrent, so we store current_item and reset it."""
            params = dict(attr)
            try:
                if 'tCenter' in params['class']:
                    # Of course we won't store current_item on first <tr class="tCenter"> seen, since there's no data yet
                    if self.tr_counter != 0:
                        # We only store current_item if torrent is still alive.
                        if self.current_item['seeds'] != None:
                            self.results.append(self.current_item)
                        else:
                            self.tr_counter -= 1 # We decrement by one to keep a good value.
                        logging.debug('do_tr: ' + str(self.current_item))
                        self.reset_current()
                    self.tr_counter += 1
            except KeyError:
                pass

        def do_a(self, attr):
            """<a> tags can specify torrent link in "href" or category or name or size in inner text. Also used to retrieve further results pages."""
            params = dict(attr)
            try:
                if self.cat_re.search(params['href']):
                    self.current_item['cat'] = True
                elif 'data-topic_id' in params and self.name_re.search(params['href']): # data-topic_id is needed to avoid conflicts.
                    self.current_item['desc_link'] = self.engine.forum_url + '/' + params['href']
                    self.current_item['link'] = self.engine.download_url + '?t=' + params['data-topic_id']
                    self.current_item['name'] = True
                elif self.current_item['size'] == False:
                    self.current_item['size'] = True
                # If we're on the first page of results, we search for other pages.
                elif self.first_page:
                    pages = self.pages_re.search(params['href'])
                    if pages:
                        if pages.group(1) not in self.other_pages:
                            self.other_pages.append(pages.group(1))
            except KeyError:
                pass

        def do_td(self, attr):
            """<td> tags give us number of leechers in inner text and can signal torrent size in next <a> tag."""
            params = dict(attr)
            try:
                if 'tor-size' in params['class']:
                    self.current_item['size'] = False
                elif 'leechmed' in params['class']:
                    self.current_item['leech'] = True
            except KeyError:
                pass

        def do_b(self, attr):
            """<b class="seedmed"> give us number of seeders in inner text."""
            params = dict(attr)
            try:
                if 'seedmed' in params['class']:
                    self.current_item['seeds'] = True
            except KeyError:
                pass

        def search(self, what, start=0):
            """Search for what starting on specified page. Defaults to first page of results."""
            logging.debug("parse_search({}, {})".format(what, start))
            
            # If we're on first page of results, we'll try to find other pages
            if start == 0:
                self.first_page = True
            else:
                self.first_page = False
            
            try:
                response = self.engine.opener.open('{}?nm={}&start={}'.format(self.engine.search_url, quote(what), start))
                # Only continue if response status is OK.
                if response.getcode() != 200:
                    raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(self.engine.search_url, response.getcode()), response.info(), None)
            except (URLError, HTTPError) as e:
                logging.error(e)
                raise e
            
            # Decode data and feed it to parser
            data = response.read().decode('cp1251')
            self.feed(data)

    def search(self, what, cat='all'):
        """Search for what on the search engine."""
        # Instantiate parser
        self.parser = self.Parser(self)
        
        # Decode search string
        what = unquote(what)
        logging.info("Searching for {}...".format(what))
        
        # Search on first page.
        logging.info("Parsing page 1.")
        self.parser.search(what)
            
        # If multiple pages of results have been found, repeat search for each page.
        logging.info("{} pages of results found.".format(len(self.parser.other_pages)+1))
        for start in self.parser.other_pages:
            logging.info("Parsing page {}.".format(int(start)//50+1))
            self.parser.search(what, start)
        
        # PrettyPrint each torrent found, ordered by most seeds
        self.parser.results.sort(key=lambda torrent:torrent['seeds'], reverse=True)
        for torrent in self.parser.results:
            torrent['engine_url'] = 'https://rutracker.org' # Kludge, see #15
            if __name__ != "__main__": # This is just to avoid printing when I debug.
                prettyPrinter(torrent)
        
        self.parser.close()
        logging.info("{} torrents found.".format(len(self.parser.results)))

# For testing purposes.
if __name__ == "__main__":
    engine = rutracker()
    engine.search('lazerhawk')
    engine.download_torrent('https://rutracker.org/forum/dl.php?t=4578927')
