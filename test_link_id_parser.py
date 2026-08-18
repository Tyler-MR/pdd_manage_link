import sys

sys.path.insert(0, r"C:\Users\Financial\wwwroot\.codex-temp\pdd_manage_link-publish2")

import api_server_v3 as api


actual = api.parse_link_id_list(" 897285113064  979640415683,982569186992\uFF0C'978888238215 ")
expected = ["897285113064", "979640415683", "982569186992", "978888238215"]
assert actual == expected, (actual, expected)
print("parse_link_id_list PASS", actual)
