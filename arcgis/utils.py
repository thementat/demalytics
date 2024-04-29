import urllib
import requests


class ArcGIS:
    def __init__(self, url):
        self.url = url

    def request(self, criteria):

        max_attempts = 100
        attempts = 0
        offset = 0

        datalist = []
        responselist = []

        requeststr = (self.url +
                      '?where=' + urllib.parse.quote(criteria) +
                      '&outFields=*' +
                      '&f=geojson')

        response = requests.get(requeststr)



        data = response.json()
        datalist.append(data)

        # if transferlimit is exceeded, keep in requesting & appending
        while ((attempts < max_attempts)
               and 'exceededTransferLimit' in data
                and len(data['features'])>0):

            offset = offset + len(data['features'])

            requeststr = (self.url +
                           '?where=' + urllib.parse.quote(criteria) +
                           '&outFields=*' +
                           '&f=geojson' +
                           '&resultOffset=' + str(offset)
                          )
            if response.status_code != 200:
                print(f'Unexpected status code: {response.status_code}. Stopping.')
                break

            response = requests.get(requeststr)
            data = response.json()
            datalist.append(data)

            if attempts == max_attempts:
                print(f'Stopped after reaching max_attempts = {max_attempts}')
                break

        features = []
        for data in datalist:
            for feature in data['features']:
                features.append(feature)

        geojson_ndjson_str = "\n".join([
            json.dumps(feature)
            for feature in features
        ]).encode('utf-8')

        return geojson_ndjson_str

