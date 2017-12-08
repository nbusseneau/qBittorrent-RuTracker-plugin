qBittorrent RuTracker plugin
===============================

qBittorrent search engine plugin for RuTracker. In case [rutracker.org](https://rutracker.org) is DNS blocked, the plugin will try to reach [official RuTracker mirrors](http://rutracker.wiki/%D0%A7%D1%82%D0%BE_%D0%B4%D0%B5%D0%BB%D0%B0%D1%82%D1%8C,_%D0%B5%D1%81%D0%BB%D0%B8_%D0%B2%D0%B0%D0%BC_%D0%B7%D0%B0%D0%B1%D0%BB%D0%BE%D0%BA%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD_%D0%B4%D0%BE%D1%81%D1%82%D1%83%D0%BF_%D0%BD%D0%B0_rutracker.org#.D0.97.D0.B5.D1.80.D0.BA.D0.B0.D0.BB.D0.B0_rutracker.org) instead.

Nothing fancy, it follows the [writing plugin guide recommandations](https://github.com/qbittorrent/search-plugins/wiki/How-to-write-a-search-plugin).

Installation
------------
* [Download the latest release.](https://github.com/Skymirrh/qBittorrent-RuTracker-plugin/releases/latest)
* Edit `rutracker.py` by replacing `YOUR_USERNAME_HERE` and `YOUR_PASSWORD_HERE` with your RuTracker username and password.
* Move `rutracker.py` and `rutracker.png` to qBittorrent search engines folder:
  * Windows: `%localappdata%\qBittorrent\nova3\engines\`
  * Linux: `~/.local/share/data/qBittorrent/nova3/engines/`
  * OS X: `~/Library/Application Support/qBittorrent/nova3/engines/`
  * *Note: If you use Python 2 instead of Python 3, replace `nova3` by `nova`.*
* RuTracker search engine should now be available.
* If no results from RuTracker appear when you search something, you should:
	* Check that RuTracker is not down.
  * Check that your credentials are correct (try to connect manually to the website by copy/pasting username and password from `rutracker.py`).