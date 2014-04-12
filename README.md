qBittorent rutracker.org plugin
===============================

qBittorrent search engine plugin for rutracker.org.

Nothing fancy, it follows the [writing plugin guide recommandations](https://github.com/qbittorrent/qBittorrent/wiki/How-to-write-a-search-plugin).

Installation
------------
First, [download the latest release](https://github.com/Skymirrh/qBittorent-rutracker-plugin/releases) and edit lines 26 and 27 of `rutracker.py` by replacing `your_username` and `your_password` with your rutracker.org username and password.

Then you should move `rutracker.py` and `rutracker.ico` to `%localappdata%\qBittorrent\nova\engines` or the Unix equivalent (I guess it would be something like `~/.local/share/data/qBittorrent/nova/engines`), and the search engine will be available in qBittorrent.
