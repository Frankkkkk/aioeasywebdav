import os
import functools
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

with open(os.path.join(os.path.dirname(__file__), "aioeasywebdav", "__version__.py")) as version_file:
    exec(version_file.read())

with open(os.path.join(os.path.dirname(__file__), "README.md")) as readme_file:
    DOC=readme_file.read()

class Tox(TestCommand):
    user_options = [('tox-args=', 'a', "Arguments to pass to tox")]
    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.tox_args = None
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True
    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import tox
        import shlex
        args = self.tox_args
        if args:
            args = shlex.split(self.tox_args)
        tox.cmdline(args=args)

setup(
    name="aioeasywebdav",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.5",
        ],
    description="A straight-forward WebDAV client, ported from easywebdav to use aiohttp.",
    long_description=DOC,
    license="ISC",
    author="Andrew Leech",
    author_email="andrew@alelec.net",
    url="http://github.com/andrewleech/aioeasywebdav",
    version=__version__,  # noqa
    packages=find_packages(exclude=["tests"]),
    data_files = [],
    install_requires=[
        "aiohttp", "six"
        ],
    tests_require=['tox'],
    cmdclass={'test': Tox},
    entry_points=dict(
        console_scripts=[],
        ),
    )
