from setuptools import setup
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='async-irc',
    version='0.1.8',
    python_requires=">=3.6",
    description="A simple asyncio.Protocol implementation designed for IRC",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/TotallyNotRobots/async-irc',
    author='linuxdaemon',
    author_email='linuxdaemon@snoonet.org',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='asyncio irc asyncirc async-irc irc-framework',
    packages=['asyncirc', 'asyncirc.util'],
    install_requires=['py-irclib'],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
)
