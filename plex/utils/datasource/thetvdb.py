import json
import requests


class TVDBHttpException(Exception):
    pass


class TVDB(object):
    base = 'https://api.thetvdb.com'

    def __init__(self, apikey=None, username=None, userkey=None):
        self.username = username
        self.userkey = userkey
        self.apikey = apikey
        self.authenticate()

    def __get_url(self, path):
        return self.base + '/' + path

    def authenticate(self):
        data = {
            'apikey': self.apikey,
        }
        if self.username and self.userkey:
            data.update({
                'username': self.username,
                'userkey': self.userkey,
            })
        response = requests.post(self.__get_url('login'),
                                 headers={
                                     'Accept': 'application/json',
                                     'Content-Type': 'application/json',
                                 },
                                 data=json.dumps(data))
        rdata = response.json()
        if response.status_code != 200:
            raise TVDBHttpException("non 200 response on login: %s" % rdata.get('Error', 'Unknown Error'))
        self.__authtok = rdata['token']

    def search(self, **kwargs):
        response = requests.get(self.__get_url('search/series'),
                                headers={
                                    'Accept': 'application/json',
                                    'Authorization': 'Bearer %s' % self.__authtok,
                                },
                                params=kwargs
                                )
        data = response.json()
        if response.status_code != 200:
            raise TVDBHttpException("non 200 response on search: %s" % data.get('Error', 'Unknown Error'))
        return data

    def series_query(self, series=0, season=0):
        response = requests.get(self.__get_url('series/{id}/episodes/query'.format(id=series)),
                                headers={
                                    'Accept': 'application/json',
                                    'Authorization': 'Bearer %s' % self.__authtok,
                                },
                                params={'airedSeason': season}
                                )
        data = response.json()
        if response.status_code != 200:
            raise TVDBHttpException("non 200 response on search: %s" % data.get('Error', 'Unknown Error'))
        return data

    def episode(self, id=0):
        response = requests.get(self.__get_url('episodes/{id}'.format(id=id)),
                                headers={
                                    'Accept': 'application/json',
                                    'Authorization': 'Bearer %s' % self.__authtok,
                                })
        data = response.json()
        if response.status_code != 200:
            raise TVDBHttpException("non 200 response on search: %s" % data.get('Error', 'Unknown Error'))
        return data


if __name__ == '__main__':
    import sys
    from pprint import pprint as pp
    from argparse import ArgumentParser
    from plex.utils.utils import s2d
    parser = ArgumentParser()
    parser.add_argument('-u', '--username', help='username')
    parser.add_argument('-k', '--userkey', help='userkey')
    parser.add_argument('-a', '--apikey', help='apikey', required=True)
    parser.add_argument('ACTION', help='what to do')
    parser.add_argument('ACTION_ARGS', help='key=val,key2=val2')

    args = parser.parse_args(sys.argv[1:])
    t = TVDB(args.apikey, args.username, args.userkey)
    pp(getattr(t, args.ACTION)(**s2d(args.ACTION_ARGS)))
