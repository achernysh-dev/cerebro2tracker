import os

from yandex_tracker_client import TrackerClient

# Do not commit real tokens — use env vars (see tests/tracker_env.py).
_token = os.environ.get("TRACKER_TOKEN")
_cloud = os.environ.get("TRACKER_CLOUD_ORG_ID")
_org = os.environ.get("TRACKER_ORG_ID")
if _token and _cloud:
    client = TrackerClient(token=_token, cloud_org_id=_cloud)
elif _token and _org:
    client = TrackerClient(token=_token, org_id=_org)
else:
    raise SystemExit("Set TRACKER_TOKEN and TRACKER_CLOUD_ORG_ID or TRACKER_ORG_ID")

print(TrackerClient)
users = client.users
fields = client.fields
for f in fields:
    print (f)
for user in users:
    print (user['firstName'],user['lastName'])

projects = client.projects
boards = client.boards
for board in boards: 
    print (board)
for project in projects:
    print (project)

# print (sys.version)
# print (3+555)