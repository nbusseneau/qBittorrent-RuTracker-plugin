# -*- coding: utf-8 -*-
"""RuTracker search engine plugin for qBittorrent."""
#VERSION: 2.00
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
]


from concurrent.futures import ThreadPoolExecutor
from html import unescape
import http.cookiejar as cookielib
import logging
import re
from tempfile import NamedTemporaryFile
from typing import Optional
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, quote, unquote
from urllib.request import build_opener, HTTPCookieProcessor

from novaprinter import prettyPrinter


# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.WARNING)


def dict_encode(dict, encoding: str='cp1251') -> dict:
    """Encode dict values to encoding (default: cp1251)."""
    encoded_dict = {}
    for key in dict:
        encoded_dict[key] = dict[key].encode(encoding)
    return encoded_dict


class rutracker(object):
    """RuTracker search engine plugin for qBittorrent."""
    name = 'RuTracker'
    url = 'https://rutracker.org' # We MUST produce an URL attribute at instantiation time, otherwise qBittorrent will fail to register the engine, see #15

    re_search_queries = re.compile(r'<a.+?href="tracker\.php?(.*?start=\d+)"')
    re_threads= re.compile(r'<tr id="trs-tr-\d+".*?</tr>', re.S)
    re_torrent_data = re.compile(
        r'data-topic_id="(?P<id>\d+?)".*?>(?P<title>.+?)<'
        r'.+?'
        r'data-ts_text="(?P<size>\d+?)"'
        r'.+?'
        r'data-ts_text="(?P<seeds>[-\d]+?)"' # seeds can be negative when distribution status does not allow downloads, see https://rutracker.org/forum/viewtopic.php?t=211216#torstatus
        r'.+?'
        r'leechmed.+?>(?P<leech>\d+?)<', re.S
    )

    @property
    def forum_url(self) -> str:
        return self.url + '/forum/'

    @property
    def login_url(self) -> str:
        return self.forum_url + 'login.php'

    def search_url(self, query: str) -> str:
        return self.forum_url + 'tracker.php?' + query

    def download_url(self, torrent_id: int) -> str:
        return self.forum_url + 'dl.php?t=' + torrent_id

    def topic_url(self, torrent_id: int) -> str:
        return self.forum_url + 'viewtopic.php?t=' + torrent_id

    def __init__(self):
        """Initialize RuTracker search engine, signing in using given credentials."""
        # Initialize various objects.
        self.cj = cookielib.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))
        self.url = self.__initialize_url() # Override url with the actual URL to be used (in case official URL isn't accessible)
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

    def __initialize_url(self):
        """Try to find a reachable RuTracker mirror."""
        errors = []
        for mirror in mirrors:
            try:
                self.opener.open(mirror)
                logging.info("Found reachable mirror: {}".format(mirror))
                return mirror
            except URLError as e:
                logging.warning("Could not resolve mirror: {}".format(mirror))
                errors.append(e)
        logging.error("Unable to resolve any RuTracker mirror -- exiting plugin search")
        raise RuntimeError("\n{}".format("\n".join([str(error) for error in errors])))

    def search(self, what: str, cat: str='all') -> None:
        """Search for what on the search engine."""
        self.results = {}
        what = unquote(what)
        logging.info("Searching for {}...".format(what))

        # Execute first search pass
        url = self.search_url('nm=' + quote(what))
        other_pages = self.__execute_search(url, is_first=True)
        logging.info("{} pages of results found.".format(len(other_pages)+1))

        # If others pages of results have been found, repeat search for each page
        with ThreadPoolExecutor() as executor:
            urls = [self.search_url(unescape(page)) for page in other_pages]
            executor.map(self.__execute_search, urls)

        logging.info("{} torrents found.".format(len(self.results)))

    def __execute_search(self, url: str, is_first: bool=False) -> Optional[list]:
        """Execute search query."""
        try:
            response = self.opener.open(url)
            # Only continue if response status is OK.
            if response.getcode() != 200:
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(url, response.getcode()), response.info(), None)
        except (URLError, HTTPError) as e:
            logging.error(e)
            raise e

        # Decode data
        data = response.read().decode('cp1251')

        # Look for threads/torrent_data
        for thread in self.re_threads.findall(data):
            match = self.re_torrent_data.search(thread)
            if match:
                torrent_data = match.groupdict()
                result = self.__build_result(torrent_data)
                self.results[torrent_data['id']] = result
                if __name__ != '__main__':
                    prettyPrinter(result)

        # If doing first search pass, look for other pages
        if is_first:
            matches = self.re_search_queries.findall(data)
            other_pages = list(dict.fromkeys(matches))
            return other_pages

    def __build_result(self, torrent_data: dict) -> dict:
        """Map torrent data to result dict as expected by prettyPrinter."""
        result = {}
        result['link'] = self.download_url(torrent_data['id'])
        result['name'] = unescape(torrent_data['title'])
        result['size'] = torrent_data['size']
        result['seeds'] = torrent_data['seeds']
        result['leech'] = torrent_data['leech']
        result['engine_url'] = 'https://rutracker.org' # We MUST use the same engine URL as the instantiation URL, otherwise downloads will fail, see #15
        result['desc_link'] = self.topic_url(torrent_data['id'])
        return result

    def download_torrent(self, url: str) -> None:
        """Download file at url and write it to a file, print the path to the file and the url."""
        # Set up fake POST params, needed to trick server into sending the file
        torrent_id = re.search(r'dl\.php\?t=(?P<id>\d+)', url).group('id')
        post_params = { 't': torrent_id, }
        
        # Download torrent file at url.
        try:
            response = self.opener.open(url, urlencode(dict_encode(post_params)).encode())
            if response.getcode() != 200: # Only continue if response status is OK
                raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(url, response.getcode()), response.info(), None)
        except (URLError, HTTPError) as e:
            logging.error(e)
            raise e

        # Write to temporary file, then print file path and url as required by plugin API
        data = response.read()
        with NamedTemporaryFile(suffix='.torrent', delete=False) as f:
            f.write(data)
            print(f.name+" "+url)

# For testing purposes.
if __name__ == "__main__":
    import timeit
    engine = rutracker()
    print(timeit.timeit(lambda: engine.search('lazerhawk'), number=1))
    print(timeit.timeit(lambda: engine.search('ubuntu'), number=1))
    print(timeit.timeit(lambda: engine.search('space'), number=1))
    print(timeit.timeit(lambda: engine.download_torrent('https://rutracker.org/forum/dl.php?t=4578927'), number=1))
