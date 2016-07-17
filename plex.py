#!/usr/bin/env python

import requests
import sys
import re
from argparse import ArgumentParser
from bs4 import BeautifulSoup as BS


class Action(object):
    def __init__(self, *args, **kwargs):
        parser = ArgumentParser()
        parser.add_argument('-u', '--username', help="username", required=True)
        parser.add_argument('-t', '--token', help="plex token", required=True)
        parser.add_argument('-H', '--host', help="plex host", required=True)

        self.add_arguments(parser)

        args = parser.parse_args(sys.argv[2:])
        for k, v in vars(args).items():
            setattr(self, k, v)

    def add_arguments(self, parser):
        pass

    def run(self):
        raise NotImplementedError

    @property
    def headers(self):
        return {
            'X-Plex-Token': self.token,
            'X-Plex-Username': self.username,
        }

    interpolate_re = re.compile(r'{{([^}]+)}}')

    def replace(self, path):
        try:
            for p in self.interpolate_re.search(path).groups():
                path = path.replace('{{%s}}' % p, getattr(self, p))
        except:
            pass
        return path

    def url(self, path):
        path = self.replace(path)
        return "http://" + ("%s%s" % (self.host, path) if path.startswith('/') else "%s/%s" % (self.host, path))

    def get(self, path='/', q={}, headers={}):
        h = self.headers
        h.update(headers)
        r = requests.get(self.url(path), params=q, headers=h)
        return r.text

    def put(self, path='/', q={}, headers={}):
        h = self.headers
        h.update(headers)
        r = requests.put(self.url(path), params=q, headers=h)
        return r.text


class List(Action):
    def add_arguments(self, parser):
        parser.add_argument('-i', '--item_id', help='item id')

    def run(self):
        if getattr(self, 'item_id', False):
            # try listing a "show" first
            body = BS(self.get('/library/sections/{{item_id}}/all'), 'xml')
            if not body.Video and not body.Directory:
                # if it's not a show it's probably a "season"
                body = BS(self.get('/library/metadata/{{item_id}}/children'), 'xml')
        else:
            body = BS(self.get('/library/sections'), 'xml')
        if body.Directory:
            print "KEY\tTYPE\tTITLE"
            for dir in body.findAll('Directory'):
                if dir['key'].find('allLeaves') != -1:
                    continue
                key = dir['key'].replace('/children', '')
                key = int(key[key.rfind('/')+1:])
                print "%4d\t%s\t%s" % (key, dir['type'], dir['title'].encode('utf8'))
        elif body.Video:
            print "%-10s %-50s %-40s" % ("KEY", "TITLE", "SORT")
            for video in body.findAll('Video'):
                key = video['key']
                key = int(key[key.rfind('/')+1:])
                print "%-10d %-50s %-40s" % (key, video['title'].encode('utf8'), video.get('titleSort', '').encode('utf8'))
        else:
            raise Exception("Unknown Section type")


class GetFile(Action):
    def add_arguments(self, parser):
        parser.add_argument('-i', '--item_id', help='item id', required=True)

    def run(self):
        body = BS(self.get('/library/metadata/{{item_id}}'), 'xml')
        print body.MediaContainer.Video.Media.Part['file']


class Update(Action):
    def add_arguments(self, parser):
        parser.add_argument('-i', '--item_id', help='item id', required=True)
        parser.add_argument('-s', '--set', help='set key=value', action='append', required=True)

    def run(self):
        q = {}
        for set in self.set:
            k, v = set.split('=', 1)
            q[k] = v
        body = BS(self.put('/library/metadata/{{item_id}}', q), 'xml')
        print body


def usage():
    print "usage: %s [list|update|getfile]" % sys.argv[0]


def main():
    if len(sys.argv) < 2:
        usage()
        raise SystemExit

    action = sys.argv[1]

    if action == 'list':
        List().run()
    elif action == 'update':
        Update().run()
    elif action == 'getfile':
        GetFile().run()
    else:
        usage()

if __name__ == '__main__':
    main()
