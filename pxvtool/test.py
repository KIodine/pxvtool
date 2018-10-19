import pypxv

test_contents = [
    {
        'illust_id': 64860518,
        'illust_page_count': 3,
        'illust_type': '0',
        'url': (
            "https://i.pximg.net/c/240x480/img-master/img/2017/09/09/04/02/55/"
            "64860518_p0_master1200.jpg"
            ),
    },
    {
        "spotlight_article_id": 5351351,
        'illust_id': 64860518,
        'illust_page_count': 3,
        'illust_type': '0',
        'url': {
            "768x1200": (
                "https://i.pximg.net/c/240x480/img-master/img/2017/09/09/04/02/55/"
                "64860518_p0_master1200.jpg"
                )
        }
    },
    {
        'illust_id': 64860518,
        'illust_page_count': 3,
        'illust_type': '2',
        'url': (
            "https://i.pximg.net/c/240x480/img-master/img/2017/09/09/04/02/55/"
            "64860518_p0_master1200.jpg"
            ),
    }
]
ext = ["jpg", "png", "zip"]

for c, ext in zip(test_contents, ext):
    testmeta = pypxv._make_illust_meta(c)
    print(testmeta)
    sampleurl = pypxv._make_sample_url(testmeta, ext)
    print(sampleurl)
    testderived = pypxv._make_derived_fields(testmeta, ext)
    print('\n'.join(map(str, testderived)))

false_content = pypxv._make_false_content(
    "https://i.pximg.net/img-master/img/2018/09/27/14/49/24/70898131_p0_master1200.jpg",
)
print(false_content)
testmeta = pypxv._make_illust_meta(false_content)
print(testmeta)
sampleurl = pypxv._make_sample_url(testmeta, "jpg")
print(sampleurl)
testderived = pypxv._make_derived_fields(testmeta, "jpg")
print("\n".join(map(str, testderived)))