# -*- coding: utf-8 -*-
"""RuTracker search engine plugin for qBittorrent."""
# VERSION: 2.20
# AUTHORS: nbusseneau (https://github.com/nbusseneau/qBittorrent-RuTracker-plugin)


class Config(object):
    # Replace `YOUR_USERNAME_HERE` and `YOUR_PASSWORD_HERE` with your RuTracker username and password
    username = "YOUR_USERNAME_HERE"
    password = "YOUR_PASSWORD_HERE"

    # Configurable list of RuTracker mirrors
    # Default: official RuTracker URLs
    mirrors = [
        "https://rutracker.org",
        "https://rutracker.net",
        "https://rutracker.nl",
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
import logging
import re
import tempfile
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


class RuTracker(object):
    """Base class for RuTracker search engine plugin for qBittorrent."""

    name = "RuTracker"
    url = DEFAULT_ENGINE_URL  # We MUST produce an URL attribute at instantiation time, otherwise qBittorrent will fail to register the engine, see #15
    encoding = "cp1251"

    re_search_queries = re.compile(r'<a.+?href="tracker\.php\?(.*?start=\d+)"')
    re_threads = re.compile(r'<tr id="trs-tr-\d+".*?</tr>', re.S)
    re_torrent_data = re.compile(
        r'a data-topic_id="(?P<id>\d+?)".*?>(?P<title>.+?)<'
        r".+?"
        r'data-ts_text="(?P<size>\d+?)"'
        r".+?"
        r'data-ts_text="(?P<seeds>[-\d]+?)"'  # Seeds can be negative when distribution status does not allow downloads, see https://rutracker.org/forum/viewtopic.php?t=211216#torstatus
        r".+?"
        r"leechmed.+?>(?P<leech>\d+?)<"
        r".+?"
        r'data-ts_text="(?P<pub_date>\d+?)"',
        re.S,
    )

    @property
    def forum_url(self) -> str:
        return self.url + "/forum/"

    @property
    def login_url(self) -> str:
        return self.forum_url + "login.php"

    def search_url(self, query: str) -> str:
        return self.forum_url + "tracker.php?" + query

    def download_url(self, query: str) -> str:
        return self.forum_url + "dl.php?" + query

    def topic_url(self, query: str) -> str:
        return self.forum_url + "viewtopic.php?" + query

    def __init__(self):
        """[Called by qBittorrent from `nova2.py` and `nova2dl.py`] Initialize RuTracker search engine, signing in using given credentials."""
        self.cj = cookielib.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))
        self.opener.addheaders = [
            ("User-Agent", ""),
            ("Accept-Encoding", "gzip, deflate"),
        ]
        self.__login()

    def __login(self) -> None:
        """Set up credentials and try to sign in."""
        self.credentials = {
            "login_username": CONFIG.username,
            "login_password": CONFIG.password,
            "login": "Вход",  # Submit button POST param is required
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
        if "bb_session" not in [cookie.name for cookie in self.cj]:
            logger.debug("cookiejar: {}".format(self.cj))
            e = ValueError("Unable to connect using given credentials.")
            logger.error(e)
            raise e
        else:
            logger.info("Login successful.")

    def search(self, what: str, cat: str = "all") -> None:
        """[Called by qBittorrent from `nova2.py`] Search for what on the search engine.

        As expected by qBittorrent API: should print to `stdout` using `prettyPrinter` for each result.
        """
        self.results = {}
        what = unquote(what)
        logger.info("Searching for {}...".format(what))

        # Execute first search pass
        url = self.search_url(urlencode({"nm": what}))
        other_pages = self.__execute_search(url, is_first=True)
        logger.info("{} pages of results found.".format(len(other_pages) + 1))

        # If others pages of results have been found, repeat search for each page
        with concurrent.futures.ThreadPoolExecutor() as executor:
            urls = [self.search_url(html.unescape(page)) for page in other_pages]
            executor.map(self.__execute_search, urls)
        logger.info("{} torrents found.".format(len(self.results)))

    def __execute_search(self, url: str, is_first: bool = False) -> list:
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
                self.results[result["id"]] = result
                if __name__ != "__main__":
                    novaprinter.prettyPrinter(result)

        # If doing first search pass, look for other pages
        if is_first:
            matches = self.re_search_queries.findall(data)
            other_pages = list(dict.fromkeys(matches))
            return other_pages

        return []

    def __build_result(self, torrent_data: dict) -> dict:
        """Map torrent data to result dict as expected by prettyPrinter."""
        query = urlencode({"t": torrent_data["id"]})
        result = {}
        result["id"] = torrent_data["id"]
        result["link"] = self.download_url(query)
        result["name"] = html.unescape(torrent_data["title"])
        result["size"] = torrent_data["size"]
        result["seeds"] = torrent_data["seeds"]
        result["leech"] = torrent_data["leech"]
        result["engine_url"] = (
            DEFAULT_ENGINE_URL  # We MUST use the same engine URL as the instantiation URL, otherwise downloads will fail, see #15
        )
        result["desc_link"] = self.topic_url(query)
        result["pub_date"] = torrent_data["pub_date"]
        return result

    def _open_url(
        self, url: str, post_params: dict[str, str] = None, log_errors: bool = True
    ) -> bytes:
        """URL request open wrapper returning response bytes if successful."""
        encoded_params = (
            urlencode(post_params, encoding=self.encoding).encode()
            if post_params
            else None
        )
        try:
            with self.opener.open(url, encoded_params or None) as response:
                logger.debug(
                    "HTTP request: {} | status: {}".format(url, response.getcode())
                )
                if response.getcode() != 200:  # Only continue if response status is OK
                    raise HTTPError(
                        response.geturl(),
                        response.getcode(),
                        "HTTP request to {} failed with status: {}".format(
                            url, response.getcode()
                        ),
                        response.info(),
                        None,
                    )
                if response.info().get("Content-Encoding") is not None:
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

    def download_torrent(self, url: str) -> None:
        """[Called by qBittorrent from `nova2dl.py`] Download torrent file and print filename + URL as required by API"""
        logger.info("Downloading {}...".format(url))
        data = self._open_url(url)
        with tempfile.NamedTemporaryFile(suffix=".torrent", delete=False) as f:
            f.write(data)
            print(f.name + " " + url)


# Register rutracker engine with nova2 (needs to match filename)
rutracker = RuTracker

# For testing purposes.
if __name__ == "__main__":
    from timeit import timeit

    logging.info("Testing RuTracker...")
    engine = RuTracker()
    logging.info("[timeit] %s", timeit(lambda: engine.search("arch linux"), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.search("ubuntu"), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.search("space"), number=1))
    logging.info("[timeit] %s", timeit(lambda: engine.search("космос"), number=1))
    logging.info(
        "[timeit] %s",
        timeit(
            lambda: engine.download_torrent(
                "https://rutracker.org/forum/dl.php?t=4578927"
            ),
            number=1,
        ),
    )
