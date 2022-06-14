from setuptools import setup

setup(
    name="pyuwb",
    version="0.0.1",
    description="A python interface for the MRASL/DECAR UWB modules",
    author="Charles Cossette and Mohammed Shalaby",
    author_email="charles.cossette@mail.mcgill.ca",
    license="MIT",
    packages=["pyuwb"],
    install_requires=["pyserial", "msgpack", "pytest"],
)
