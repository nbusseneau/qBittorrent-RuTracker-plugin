from setuptools import setup

setup(
    name="qbittorrent-rutracker",
    version="1.2.0",
    packages=["qbit_rutracker"],
    python_requires=">=3.6",
    install_requires=[
        "click>=7.0",
        "beautifulsoup4>=4.8.0",
        "requests>=2.22.0",
        "humanfriendly>=4.18",
    ],
    tests_require=["pytest>=5.1.1"],
    package_data={
        "qbit_rutracker": ["*.txt", "*.png"]
    }
)

