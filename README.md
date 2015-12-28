qBittorent rutracker.org plugin
===============================

qBittorrent search engine plugin for rutracker.org.

Nothing fancy, it follows the [writing plugin guide recommandations](https://github.com/qbittorrent/qBittorrent/wiki/How-to-write-a-search-plugin).

Installation
------------
* [Download the latest release.](https://github.com/Skymirrh/qBittorent-rutracker-plugin/releases/latest)
* Edit `rutracker.py` by replacing `YOUR_USERNAME_HERE` and `YOUR_PASSWORD_HERE` with your rutracker.org username and password.
* Move `rutracker.py` and `rutracker.png` to qBittorrent search engines folder:
  * Windows: `%localappdata%\qBittorrent\nova3\engines\`
  * Linux: `~/.local/share/data/qBittorrent/nova3/engines/`
  * OS X: `~/Library/Application Support/qBittorrent/nova3/engines/`
  * *Note: If you use Python 2 instead of Python 3, replace `nova3` by `nova`.*
* rutracker.org search engine should now be available.
* If no results from rutracker.org appear when you search something, you should:
	* Check that rutracker.org is not down.
  * Check that your credentials are correct (try to connect manually to the website by copy/pasting username and password from `rutracker.py`).