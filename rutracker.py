# -*- coding: utf-8 -*-
"""RuTracker search engine plugin for qBittorrent."""
#VERSION: 2.00
#AUTHORS: Skymirrh (skymirrh@gmail.com)

# Replace YOUR_USERNAME_HERE and YOUR_PASSWORD_HERE with your RuTracker username and password
CREDENTIALS = {
    'login_username': u'YOUR_USERNAME_HERE',
    'login_password': u'YOUR_PASSWORD_HERE',
}

# List of RuTracker mirrors
MIRRORS = [
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
from urllib.parse import quote, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import build_opener, HTTPCookieProcessor

from novaprinter import prettyPrinter


# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.WARNING)


class rutracker(object):
    """RuTracker search engine plugin for qBittorrent."""
    name = 'RuTracker'
    url = 'https://rutracker.org' # We MUST produce an URL attribute at instantiation time, otherwise qBittorrent will fail to register the engine, see #15
    encoding = 'cp1251'

    re_search_queries = re.compile(r'<a.+?href="tracker\.php\?(.*?start=\d+)"')
    re_threads = re.compile(r'<tr id="trs-tr-\d+".*?</tr>', re.S)
    re_torrent_data = re.compile(
        r'data-topic_id="(?P<id>\d+?)".*?>(?P<title>.+?)<'
        r'.+?'
        r'data-ts_text="(?P<size>\d+?)"'
        r'.+?'
        r'data-ts_text="(?P<seeds>[-\d]+?)"' # Seeds can be negative when distribution status does not allow downloads, see https://rutracker.org/forum/viewtopic.php?t=211216#torstatus
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

    def download_url(self, query: str) -> str:
        return self.forum_url + 'dl.php?' + query

    def topic_url(self, query: str) -> str:
        return self.forum_url + 'viewtopic.php?' + query

    def __init__(self):
        """[Called by qBittorrent from `nova2.py` and `nova2dl.py`] Initialize RuTracker search engine, signing in using given credentials."""
        self.cj = cookielib.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))

        # If mirror list was updated, check for a reachable mirror immediately
        # Otherwise this will be lazily checked on first login attempt
        if self.url != MIRRORS[0]:
            self.url = self.__check_mirrors()

        self.__login()

    def __login(self) -> None:
        """Set up credentials and try to sign in."""
        self.credentials = CREDENTIALS
        self.credentials['login'] = u'Вход' # Submit button POST param is required

        # Try to sign in, and try switching to a mirror on failure
        self.__open_url(self.login_url, self.credentials, check_mirrors=True)

        # Check if login was successful using cookies
        if not 'bb_session' in [cookie.name for cookie in self.cj]:
            logging.debug(self.cj)
            e = ValueError("Unable to connect using given credentials.")
            logging.error(e)
            raise e
        else:
            logging.info("Login successful.")

    def search(self, what: str, cat: str='all') -> None:
        """[Called by qBittorrent from `nova2.py`] Search for what on the search engine."""
        self.results = {}
        what = unquote(what)
        logging.info("Searching for {}...".format(what))

        # Execute first search pass
        url = self.search_url(urlencode({ 'nm': quote(what) }))
        other_pages = self.__execute_search(url, is_first=True)
        logging.info("{} pages of results found.".format(len(other_pages)+1))

        # If others pages of results have been found, repeat search for each page
        with ThreadPoolExecutor() as executor:
            urls = [self.search_url(unescape(page)) for page in other_pages]
            executor.map(self.__execute_search, urls)

        logging.info("{} torrents found.".format(len(self.results)))

    def __execute_search(self, url: str, is_first: bool=False) -> Optional[list]:
        """Execute search query."""
        # Execute search query at URL and decode response bytes
        data = self.__open_url(url).decode(self.encoding)

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
        query = urlencode({ 't': torrent_data['id'] })
        result = {}
        result['link'] = self.download_url(query)
        result['name'] = unescape(torrent_data['title'])
        result['size'] = torrent_data['size']
        result['seeds'] = torrent_data['seeds']
        result['leech'] = torrent_data['leech']
        result['engine_url'] = 'https://rutracker.org' # We MUST use the same engine URL as the instantiation URL, otherwise downloads will fail, see #15
        result['desc_link'] = self.topic_url(query)
        return result

    def download_torrent(self, url: str) -> None:
        """[Called by qBittorrent from `nova2dl.py`] Download file at url and write it to a file, print the path to the file and the url."""
        # Download torrent file bytes
        data = self.__open_url(url)

        # Write to temporary file, then print file path and URL as required by plugin API
        with NamedTemporaryFile(suffix='.torrent', delete=False) as f:
            f.write(data)
            print(f.name + " " + url)

    def __open_url(self, url: str, post_params=None, check_mirrors=False) -> bytes:
        """URL request open wrapper returning response bytes if successful."""
        encoded_params = urlencode(post_params, encoding=self.encoding).encode() if post_params else None
        try:
            with self.opener.open(url, encoded_params or None) as response:
                if response.getcode() != 200: # Only continue if response status is OK
                    raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(url, response.getcode()), response.info(), None)
                return response.read()
        except (URLError, HTTPError) as e:
            if check_mirrors:
                # If a reachable mirror is found, update engine URL and retry request with new base URL
                self.url = self.__check_mirrors()
                new_url = list(urlsplit(url))
                new_url[0:2] = urlsplit(self.url)[0:2]
                new_url = urlunsplit(new_url)
                self.__open_url(new_url, post_params, check_mirrors=False)
            else:
                logging.error(e)
                raise e

    def __check_mirrors(self) -> str:
        """Try to find a reachable RuTracker mirror."""
        errors = []
        for mirror in MIRRORS:
            try:
                self.opener.open(mirror)
                logging.info("Found reachable mirror: {}".format(mirror))
                return mirror
            except URLError as e:
                logging.warning("Could not resolve mirror: {}".format(mirror))
                errors.append(e)
        logging.error("Unable to resolve any RuTracker mirror -- exiting plugin search")
        raise RuntimeError("\n{}".format("\n".join([str(error) for error in errors])))


# For testing purposes.
if __name__ == "__main__":
    import timeit
    engine = rutracker()
    print(timeit.timeit(lambda: engine.search('lazerhawk'), number=1))
    print(timeit.timeit(lambda: engine.search('ubuntu'), number=1))
    print(timeit.timeit(lambda: engine.search('space'), number=1))
    print(timeit.timeit(lambda: engine.download_torrent('https://rutracker.org/forum/dl.php?t=4578927'), number=1))
