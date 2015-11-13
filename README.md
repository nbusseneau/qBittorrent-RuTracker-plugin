qBittorent rutracker.org plugin
===============================

qBittorrent search engine plugin for rutracker.org.

Nothing fancy, it follows the [writing plugin guide recommandations](https://github.com/qbittorrent/qBittorrent/wiki/How-to-write-a-search-plugin).

Installation
------------
* [Download the latest release](https://github.com/Skymirrh/qBittorent-rutracker-plugin/releases)
* Edit lines 26 and 27 of `rutracker.py` by replacing `YOUR_USERNAME_HERE` and `YOUR_PASSWORD_HERE` with your rutracker.org username and password.
* Move `rutracker.py` and `rutracker.png` to qBittorrent Python 3 engines folder:
  * Windows: `%localappdata%\qBittorrent\nova3\engines\`
  * Linux: `~/.local/share/data/qBittorrent/nova3/engines/`
  * OS X: `~/Library/Application Support/qBittorrent/nova3/engines/`
  * *Note: If you use Python 2, the `nova3` folder will be named `nova` instead.*
* qBittorrent should now be available.