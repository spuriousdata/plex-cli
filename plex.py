#!/usr/bin/env python

import requests
import sys
import re
from pprint import pprint as pp
from argparse import ArgumentParser
from bs4 import BeautifulSoup as BS
from plex.utils.datasource.thetvdb import TVDB


class Action(object):
    def __init__(self, *args, **kwargs):
        if kwargs.pop('__NOPARSER__', False):
            return
        parser = ArgumentParser()
        parser.add_argument('-u', '--username', help="username", required=True)
        parser.add_argument('-t', '--token', help="plex token", required=True)
        parser.add_argument('-H', '--host', help="plex host", required=True)

        self.add_arguments(parser)

        args = parser.parse_args(sys.argv[2:])
        for k, v in vars(args).items():
            setattr(self, k, v)

    @classmethod
    def from_kwargs(cls, **kwargs):
        new = cls(__NOPARSER__=True)
        for k, v in kwargs.items():
            setattr(new, k, v)
        return new

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
        parser.add_argument('-e', '--extra_metadata',
                            help="Additional metadata Fields to show", action='append')

    def run(self, raw=False):  # noqa: ignore=C901
        if getattr(self, 'item_id', False):
            # try listing a "show" first
            body = BS(self.get('/library/sections/{{item_id}}/all'), 'xml')
            if not body.Video and not body.Directory:
                # if it's not a show it's probably a "season"
                body = BS(self.get('/library/metadata/{{item_id}}/children'), 'xml')
        else:
            body = BS(self.get('/library/sections'), 'xml')
        if raw:
            return body
        if body.Directory:
            print "KEY\tTYPE\tTITLE" + ('\t'.join(self.extra_metadata) if self.extra_metadata else '')
            for dir in body.findAll('Directory'):
                if dir['key'].find('allLeaves') != -1:
                    continue
                key = dir['key'].replace('/children', '')
                key = int(key[key.rfind('/')+1:])
                fmt_string = "{key:>10d}\t{type}\t{title}"
                extra = {}
                if self.extra_metadata:
                    for ef in self.extra_metadata:
                        value = dir.get(ef, None)
                        extra[ef] = value
                        fmt_string += "\t{{{ef}:>20}}".format(ef=ef)
                print fmt_string.format(key=key, type=dir['type'], title=dir['title'].encode('utf8'), **extra)
        elif body.Video:
            print "{:>10s} {:>50s} {:>40s}".format("KEY", "TITLE", "SORT"),
            if self.extra_metadata:
                for m in self.extra_metadata:
                    print "{:>20}".format(m),
            print
            for video in body.findAll('Video'):
                key = video['key']
                key = int(key[key.rfind('/')+1:])
                fmt_string = "{key:>10d} {title:>50s} {titleSort:>40s}"
                extra = {}
                if self.extra_metadata:
                    for ef in self.extra_metadata:
                        value = video.get(ef, None)
                        extra[ef] = value
                        fmt_string += "\t{{{ef}:>20}}".format(ef=ef)
                print fmt_string.format(key=key, title=video['title'].encode('utf8'), titleSort=video.get('titleSort', '').encode('utf8'), **extra)
        elif body.html.head.title.text == "Unauthorized":
            raise Exception("Unauthorized: The Plex Token probably changed")
        else:
            print body
            raise Exception("Unknown Section type")


class GetFile(Action):
    def add_arguments(self, parser):
        parser.add_argument('-i', '--item_id', help='item id', required=True)

    def run(self):
        body = BS(self.get('/library/metadata/{{item_id}}'), 'xml')
        print body.MediaContainer.Video.Media.Part['file'].encode('utf-8')


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


class UpdateSeason(Action):
    def add_arguments(self, parser):
        parser.add_argument('-i', '--item_id', help='item id', required=True)
        parser.add_argument('-S', '--series_id', help='TVDB', required=True)
        parser.add_argument('-s', '--season', help='season number', required=True)
        parser.add_argument('-a', '--apikey', help='apikey', required=True)
        parser.add_argument('-F', '--fields', help='title,summary,originallyAvailableAt', default='title,sumary,originallyAvailableAt')
        parser.add_argument('-W', '--write', help='actually write data (as opposed to just printing what would write)', default=False, action='store_true')
        parser.add_argument('-p', '--use_production_code', help='use production code as episode number', default=False, action='store_true')
        parser.add_argument('-o', '--omit', help='skip episode number (specify multiple times)', action='append', type=int)
        parser.add_argument('-P', '--force_ep_number', help='force episode number for an item to be a specific value eg. "12:17". Forces API data episode "12" to be used as episode "17"', action='append')

    def run(self):  # noqa ignore:C901
        self.forced_numbers = {}
        if self.force_ep_number:
            self.forced_numbers = dict((int(y[0]), int(y[1])) for y in [x.split(':') for x in self.force_ep_number])
        t = TVDB(self.apikey)
        tdata = t.series_query(self.series_id, self.season)['data']
        if self.use_production_code:
            pc = re.compile(r'(\d\d)H?$')
            new_tdata = []
            for i in tdata:
                new = t.episode(i['id'])['data']
                if self.forced_numbers and self.forced_numbers.get(new['airedEpisodeNumber'], False):
                    new['production_episode_number'] = self.forced_numbers[new['airedEpisodeNumber']]
                    # print "Setting %d to %d: %s" % (new['airedEpisodeNumber'], self.forced_numbers[new['airedEpisodeNumber']], new['episodeName'])
                else:
                    try:
                        new['production_episode_number'] = pc.search(new['productionCode']).group(1)
                    except:
                        new['production_episode_number'] = new['airedEpisodeNumber']
                        # pp(new)
                        # raise
                new_tdata.append(new)
            tdata = new_tdata

        _kwargs = self.__dict__
        _kwargs['extra_metadata'] = ['index']
        plex_season = List.from_kwargs(**_kwargs)

        fields = self.fields.split(',')
        data = plex_season.run(raw=True)
        for video in data.findAll('Video'):
            if self.omit and int(video['index']) in self.omit:
                continue

            if self.use_production_code:
                try:
                    tv_video = filter(lambda x: int(x['production_episode_number']) == int(video['index']), tdata)[0]
                except:
                    print "Video: %d: %s" % (int(video['index']), video['title'])
                    pp([(x['airedEpisodeNumber'], x['production_episode_number'], x['episodeName']) for x in tdata])
                    raise
            else:
                tv_video = filter(lambda x: int(x['airedEpisodeNumber']) == int(video['index']), tdata)[0]
            update = {}

            printlines = [video.Media.Part['file'].rsplit('/', 1)[1]]

            if 'summary' in fields and video['summary'] != tv_video['overview']:
                printlines.append("\t" + video['summary'] + "  -->  " + tv_video['overview'])
                update['summary'] = tv_video['overview']

            if 'title' in fields and video['title'] != tv_video['episodeName']:
                printlines.append("\t" + video['title'] + "  -->  " + tv_video['episodeName'])
                update['title'] = tv_video['episodeName']

            if 'originallyAvailableAt' in fields and video['originallyAvailableAt'] != tv_video['firstAired']:
                printlines.append("\t" + video['originallyAvailableAt'] + "  -->  " + tv_video['firstAired'])
                printlines.append("\t" + video['year'] + "  -->  " + tv_video['firstAired'].split('-')[0])
                update['originallyAvailableAt'] = tv_video['firstAired']
                update['year'] = tv_video['firstAired'].split('-')[0]

            if update:
                for p in printlines:
                    print p

            if self.write and update:
                self.put('/library/metadata/%s' % video['ratingKey'], update)
                print "Updated!"


def usage():
    print "usage: %s [list|update|getfile|update_season]" % sys.argv[0]


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
    elif action == 'update_season':
        UpdateSeason().run()
    else:
        usage()

if __name__ == '__main__':
    main()

