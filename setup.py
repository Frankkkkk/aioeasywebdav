import os
import functools
from setuptools import setup, find_packages

_IN_PACKAGE_DIR = functools.partial(os.path.join, "aioeasywebdav")

with open(_IN_PACKAGE_DIR("__version__.py")) as version_file:
    exec(version_file.read())

properties = dict(
    name="aioeasywebdav",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.5",
        ],
    description="A straight-forward WebDAV client, implemented using aiohttp",
    license="ISC",
    author="Andrew Leech",
    author_email="andrew@alelec.net",
    url="http://github.com/andrewleech/aioeasywebdav",
    version=__version__,  # noqa
    packages=find_packages(exclude=["tests"]),
    data_files = [],
    install_requires=[
        "aiohttp",
        ],
    entry_points=dict(
        console_scripts=[],
        ),
    )

# Properties for development environments
if "aioeasywebdav_DEV" in os.environ:
    properties["install_requires"].append((
        "nose",
        "yanc",
        "PyWebDAV",
        ))

setup(**properties)