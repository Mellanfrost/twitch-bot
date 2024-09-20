from setuptools import setup

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="twitch_bot",
    version="0.1.0",
    packages=["twitch_bot"],
    install_requires=requirements,
    url="https://github.com/Mellanfrost/twitch-bot",
    author="Mellanfrost",
)
