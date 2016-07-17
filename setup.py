from setuptools import setup

setup(
    name="plex-cli",
    version="0.0.1",
    scripts=["plex.py"],
    install_requires=[
        "requests>=2.10.0",
        "beautifulsoup4>=4.4.1",
        "lxml>=3.6.0"
    ],
    author="Mike O'Malley",
    author_email="spuriousdata@gmail.com",
    license="MIT",
    url="https://github.com/spuriousdata/plex-cli",
)
