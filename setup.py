import setuptools
from sys import platform

with open("README.md", "r") as fh:
    long_description = fh.read()

install_requires = ["httpx==0.14.*",
                    "audible_kennedn @ https://github.com/kennedn/Audible/tarball/master#egg=audible_kennedn-0.5dev0"]
if platform == "linux" or platform == "linux2":
    install_requires.extend(("pyudev", "psutil"))

setuptools.setup(
    name="kindlepass",
    version="0.2",
    author="kennedn",
    author_email="kennedn@msn.com",
    description="Helps older Kindle models continue to use the Audible service",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kennedn/kindlepass",
    packages=["kindlepass"],
    entry_points={
        "console_scripts": [
            "kindlepass = kindlepass.kindlepass:main",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=install_requires,
    python_requires='>=3.6',
)
