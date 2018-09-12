from distutils.core import setup

desc = '''\
Pixiv ranking and spotlight download tool.\
'''

setup(
    name="pxvtool",
    version="2.0.5",
    description=desc,
    author="337",
    license="MIT",
    packages=["pxvtool"],
    python_requires=">=3.6",
    install_requires=[
        "aiohttp",
    ],
    zip_safe=False
)