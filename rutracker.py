# -*- coding: utf-8 -*-
"""RuTracker search engine plugin for qBittorrent."""
#VERSION: 2.19
#AUTHORS: nbusseneau (https://github.com/nbusseneau/qBittorrent-RuTracker-plugin)

class Config(object):
    # Replace `YOUR_USERNAME_HERE` and `YOUR_PASSWORD_HERE` with your RuTracker username and password
    # Do not remove the `u` marker nor the '' quote characters
    username = u'YOUR_USERNAME_HERE'
    password = u'YOUR_PASSWORD_HERE'

    # If you want to use magnet links instead of torrent files for downloading, uncomment `download_type`
    # download_type = 'MAGNET_LINK'

    # Configurable list of RuTracker mirrors
    # Default: official RuTracker URLs
    mirrors = [
        'https://rutracker.org',
        'https://rutracker.net',
        'https://rutracker.nl',
    ]

    # Configurable list of RuTracker API mirrors
    # Default: official RuTracker API
    # Only used when download_type is set to 'MAGNET_LINK'
    api_mirrors = [
        'https://api.t-ru.org/v1/',
    ]

CONFIG = Config()
DEFAULT_ENGINE_URL = CONFIG.mirrors[0]
# note: the default engine URL is only used for display purposes in the
# qBittorrent UI. If the first mirror configured above is not reachable, the
# actual tracker / download / page URLs will instead be based off one of the
# reachable ones despite the displayed URL not having changed in the UI. See
# https://github.com/nbusseneau/qBittorrent-RuTracker-plugin/issues/15 for more
# details and discussion.


import concurrent.futures
import html
import http.cookiejar as cookielib
import gzip
import json
import logging
import random
import re
import tempfile
from typing import Optional
from urllib.error import URLError, HTTPError
from urllib.parse import unquote, urlencode
from urllib.request import build_opener, HTTPCookieProcessor

try:
    import novaprinter
except ImportError:
    # When novaprinter is not immediately known as a local module, dynamically
    # import novaprinter from current or parent directory, allowing to run both
    # `python engines/rutracker.py` from `nova3` or `python rutracker.py` from
    # `nova3/engines` without issue
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("novaprinter", "nova2.py")
        novaprinter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(novaprinter)
    except FileNotFoundError:
        spec = importlib.util.spec_from_file_location("novaprinter", "../nova2.py")
        novaprinter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(novaprinter)


# Setup logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger()


class RuTrackerBase(object):
    """Base class for RuTracker search engine plugin for qBittorrent."""
    name = 'RuTracker'
    url = DEFAULT_ENGINE_URL # We MUST produce an URL attribute at instantiation time, otherwise qBittorrent will fail to register the engine, see #15
    encoding = 'cp1251'

    re_search_queries = re.compile(r'<a.+?href="tracker\.php\?(.*?start=\d+)"')
    re_threads = re.compile(r'<tr id="trs-tr-\d+".*?</tr>', re.S)
    re_torrent_data = re.compile(
        r'a data-topic_id="(?P<id>\d+?)".*?>(?P<title>.+?)<'
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
        self.opener.addheaders = [
            ('User-Agent', ''),
            ('Accept-Encoding', 'gzip, deflate'),
        ]
        self.__login()

    def __login(self) -> None:
        """Set up credentials and try to sign in."""
        self.credentials = {
            'login_username': CONFIG.username,
            'login_password': CONFIG.password,
            'login': u'Вход' # Submit button POST param is required
        }

        # Try to sign in, and try switching to a mirror on failure
        try:
            self._open_url(self.login_url, self.credentials, log_errors=False)
        except (URLError, HTTPError):
            # If a reachable mirror is found, update engine URL and retry request with new base URL
            logging.info("Checking for RuTracker mirrors...")
            self.url = self._check_mirrors(CONFIG.mirrors)
            self._open_url(self.login_url, self.credentials)

        # Check if login was successful using cookies
        if not 'bb_session' in [cookie.name for cookie in self.cj]:
            logger.debug("cookiejar: {}".format(self.cj))
            e = ValueError("Unable to connect using given credentials.")
            logger.error(e)
            raise e
        else:
            logger.info("Login successful.")

    def search(self, what: str, cat: str='all') -> None:
        """[Called by qBittorrent from `nova2.py`] Search for what on the search engine.
        
        As expected by qBittorrent API: should print to `stdout` using `prettyPrinter` for each result.
        """
        self.results = {}
        what = unquote(what)
        logger.info("Searching for {}...".format(what))

        # Execute first search pass
        url = self.search_url(urlencode({ 'nm': what }))
        other_pages = self.__execute_search(url, is_first=True)
        logger.info("{} pages of results found.".format(len(other_pages)+1))

        # If others pages of results have been found, repeat search for each page
        with concurrent.futures.ThreadPoolExecutor() as executor:
            urls = [self.search_url(html.unescape(page)) for page in other_pages]
            executor.map(self.__execute_search, urls)

        # Call "done" handler once done
        self._search_done_handler()

    def __execute_search(self, url: str, is_first: bool=False) -> Optional[list]:
        """Execute search query."""
        # Execute search query at URL and decode response bytes
        data = self._open_url(url).decode(self.encoding)

        # Look for threads/torrent_data
        for thread in self.re_threads.findall(data):
            match = self.re_torrent_data.search(thread)
            if match:
                torrent_data = match.groupdict()
                logger.debug("Torrent data: {}".format(torrent_data))
                result = self.__build_result(torrent_data)
                self.results[result['id']] = result
                self._result_handler(result)

        # If doing first search pass, look for other pages
        if is_first:
            matches = self.re_search_queries.findall(data)
            other_pages = list(dict.fromkeys(matches))
            return other_pages

    def __build_result(self, torrent_data: dict) -> dict:
        """Map torrent data to result dict as expected by prettyPrinter."""
        query = urlencode({ 't': torrent_data['id'] })
        result = {}
        result['id'] = torrent_data['id']
        result['link'] = self.download_url(query)
        result['name'] = html.unescape(torrent_data['title'])
        result['size'] = torrent_data['size']
        result['seeds'] = torrent_data['seeds']
        result['leech'] = torrent_data['leech']
        result['engine_url'] = DEFAULT_ENGINE_URL # We MUST use the same engine URL as the instantiation URL, otherwise downloads will fail, see #15
        result['desc_link'] = self.topic_url(query)
        return result

    def _result_handler(self, result: dict) -> None:
        """Print result to stdout according to qBittorrent API. Will be overriden by subclasses for specific processing."""
        if __name__ != '__main__':
            novaprinter.prettyPrinter(result)

    def _search_done_handler(self) -> None:
        """Log total number of results. Will be overriden by subclasses for specific processing."""
        logger.info("{} torrents found.".format(len(self.results)))

    def _open_url(self, url: str, post_params: dict[str, str]=None, log_errors: bool=True) -> bytes:
        """URL request open wrapper returning response bytes if successful."""
        encoded_params = urlencode(post_params, encoding=self.encoding).encode() if post_params else None
        try:
            with self.opener.open(url, encoded_params or None) as response:
                logger.debug("HTTP request: {} | status: {}".format(url, response.getcode()))
                if response.getcode() != 200: # Only continue if response status is OK
                    raise HTTPError(response.geturl(), response.getcode(), "HTTP request to {} failed with status: {}".format(url, response.getcode()), response.info(), None)
                if response.info().get('Content-Encoding') is not None:
                    return gzip.decompress(response.read())
                else:
                    return response.read()
        except (URLError, HTTPError) as e:
            if log_errors:
                logger.error(e)
            raise e

    def _check_mirrors(self, mirrors: list) -> str:
        """Try to find a reachable mirror in given list and return its URL."""
        errors = []
        for mirror in mirrors:
            try:
                self.opener.open(mirror)
                logger.info("Found reachable mirror: {}".format(mirror))
                return mirror
            except URLError as e:
                logger.warning("Could not resolve mirror: {}".format(mirror))
                errors.append(e)
        logger.error("Unable to resolve any mirror")
        raise RuntimeError("\n{}".format("\n".join([str(error) for error in errors])))


class RuTrackerTorrentFiles(RuTrackerBase):
    """Regular search engine downloading torrents via torrent files.
    
    Since RuTracker torrent files require to be authenticated for downloading,
    this version registers the `download_torrent` function, which will be called
    by qBittorrent to download files through the plugin.
    """
    def download_torrent(self, url: str) -> None:
        """[Called by qBittorrent from `nova2dl.py`] Download torrent file and print filename + URL as required by API"""
        logger.info("Downloading {}...".format(url))
        filename = self.__download_torrent_file(url)
        print(filename + " " + url)

    def __download_torrent_file(self, url: str) -> None:
        """Download torrent file at URL, write to a local temporary file, and return filename."""
        # Download torrent file bytes
        data = self._open_url(url)

        # Write to temporary file, then print file path and URL as required by plugin API
        with tempfile.NamedTemporaryFile(suffix='.torrent', delete=False) as f:
            f.write(data)
            return f.name


class RuTrackerMagnetLinks(RuTrackerBase):
    """Alternative search engine downloading torrents via magnet links.
    
    This version is not recommended for general usage:
    - It uses the RuTracker API for retrieving torrent hashes, but this may be
      blocked for you and to my knowledge there are no mirrors at the moment.
    - (Minor) Retrieving torrents via magnet links is slower than torrent files
      because of the handshake process, especially if your connection is slow
      or rate-limited and has troubles connecting to DHT/tracker.
    - (Minor) This version of the search engine returns result in batches based
      on the API `get_limit` limit for query parameters. It will be less
      responsive than the regular version, especially for searches with a huge
      number of results and if your connection is slow or rate-limited.

    It is however usable from the web GUI, whereas the regular version cannot be
    used with the web GUI until https://github.com/qbittorrent/qBittorrent/issues/11150
    is fixed.

    Since magnet links are self-sufficient, RuTracker authentication data is not
    required for downloading. This version simply does not register the
    `download_torrent` function expected by the qBittorrent API, in which case
    qBittorrent simply directly uses result 'link' to download.
    """

    # RuTracker announcers to be added to magnet links
    announcers = [
        'bt.t-ru.org',
        'bt2.t-ru.org',
        'bt3.t-ru.org',
        'bt4.t-ru.org',
    ]
    api_url = CONFIG.api_mirrors[0]

    @property
    def limit_url(self) -> str:
        return self.api_url + 'get_limit'

    @property
    def hash_url(self) -> str:
        return self.api_url + 'get_tor_hash'

    def download_url(self, magnet_hash: str) -> str:
        """Override default download URL and replace it with a magnet link."""
        announcer = random.choice(self.announcers)
        return 'magnet:?xt=urn:btih:{}&tr=http://{}/ann?magnet'.format(magnet_hash, announcer)

    def __init__(self):
        super().__init__()
        self.limit = self.__get_limit()

    def __get_limit(self) -> int:
        """Retrieve RuTracker API limit when passing values to API operations."""
        try:
            data = self._open_url(self.limit_url, log_errors=False)
        except (URLError, HTTPError):
            # If a reachable mirror is found, update API URL and retry request with new base URL
            logging.info("Checking for RuTracker API mirrors...")
            self.api_url = self._check_mirrors(CONFIG.api_mirrors)
            data = self._open_url(self.limit_url, self.credentials)
        json_data = json.loads(data)
        logging.debug("get limit | json: {}".format(json_data))
        return json_data['result']['limit']

    def _result_handler(self, result: dict) -> None:
        """Explicitly do nothing as we want to process results ourselves for magnet links."""
        pass

    def _search_done_handler(self) -> None:
        """Build magnet links with the help of RuTracker API after retrieving results, then print to stdout according to qBittorrent API."""
        all_ids = [torrent_id for torrent_id in self.results.keys()]
        for chunk in _chunks(all_ids, self.limit):
            for torrent_id, magnet_hash in self.__retrieve_magnet_hashes(chunk).items():
                self.results[torrent_id]['link'] = self.download_url(magnet_hash)
        
        for result in self.results.values():
            if __name__ != '__main__':
                novaprinter.prettyPrinter(result)
        
        super()._search_done_handler()

    def __retrieve_magnet_hashes(self, chunk: list) -> dict:
        """Use RuTracker API to retrieve magnet hashes for a given list of torrent IDs."""
        query = {
            'by': 'topic_id',
            'val': ','.join(chunk),
        }
        data = self._open_url(self.hash_url, query)
        json_data = json.loads(data)
        logging.debug("retrieve hashes | json: {}".format(json_data))
        return json_data['result']


def _chunks(l: list, n: int) -> list:
    """Yield chunks of max size n from given list."""
    for i in range(0, len(l), n):
        yield l[i:i+n]


# If configured for using magnet links, register RuTrackerMagnetLinks as engine
# Otherwise default to registering RuTrackerTorrentFiles
if hasattr(CONFIG, 'download_type') and CONFIG.download_type == 'MAGNET_LINK':
    rutracker = RuTrackerMagnetLinks
else:
    rutracker = RuTrackerTorrentFiles


# For testing purposes.
if __name__ == "__main__":
    from timeit import timeit
    logging.info("Testing rutracker...")
    engine = rutracker()
    logging.info("'{}' registered as 'rutracker'".format(type(engine)))

    logging.info("Testing RuTrackerTorrentFiles...")
    engine = RuTrackerTorrentFiles()
    logging.info("[timeit] %s", timeit(lambda: engine.search('arch linux'), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.search('ubuntu'), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.search('space'), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.search('космос'), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.download_torrent('https://rutracker.org/forum/dl.php?t=4578927'), number=1))

    logging.info("Testing RuTrackerMagnetLinks...")
    engine = RuTrackerMagnetLinks()
    logging.info("[timeit] %s", timeit(lambda: engine.search('arch linux'), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.search('ubuntu'), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.search('space'), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.search('космос'), number=1))
