# pindead
Searches for dead links in your [Pinboard](https://pinboard.in) bookmarks and optionally deletes any that do not return a `200 OK` from a request.

_Requires Python 3.6 and up_

### Setup
Set these two values in your environment:

```
export PINBOARD_EMAIL="yourusername@maildomain.com"
export PINBOARD_TOKEN="username:XXXXXXXXXXXXXXXXXXX"
```

To find out what your Pinboard API token is, go here:

https://pinboard.in/settings/password

### Excecution
```
python pindead.py
```

### Example run
![Pindead example screen shot](screenshot.png?raw=true)
