from pypxv import _tear_down

sample_url = \
    "https://i.pximg.net/img-original/img/2018/10/02/08/04/56/70981001_p1.jpg"

down = _tear_down(sample_url, 2)

for d in down:
    print(d)