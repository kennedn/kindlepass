import setuptools
from sys import platform

with open("README.md", "r") as fh:
    long_description = fh.read()

install_requires = ["httpx==0.14.*", 
                    "audible_kennedn @ git+https://github.com/kennedn/Audible#egg=audible_kennedn-0.5dev0"]
if platform == "linux" or platform == "linux2":
    install_requires.extend(("pyudev", "psutil"))

setuptools.setup(
    name="KindleAuthenticator-kennedn",
    version="0.1",
    author="kennedn",
    author_email="kennedn@msn.com",
    description="Helps older Kindle models continue to use the Audible service",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kennedn/KindleActivator",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=install_requires,
    python_requires='>=3.6',
)