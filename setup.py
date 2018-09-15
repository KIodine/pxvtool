from distutils.core import setup

desc = '''\
Pixiv ranking and spotlight download tool.\
'''

setup(
    name="pxvtool",
    version="1.1.0",
    description=desc,
    author="KIodine",
    license="MIT",
    packages=["pxvtool"],
    python_requires=">=3.6",
    install_requires=[
        "aiohttp",
    ],
    zip_safe=False
)