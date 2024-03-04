import json
import requests



class Source:
    def __init__(self, source_id, username, token):
        self.source_id = source_id
        self.username = username
        self.token = token
        self.base_url = f'https://api.mapbox.com/tilesets/v1/sources/{self.username}/{self.source_id}?access_token={self.token}'

    def upload(self, file_name, file_data):
        response = requests.post(
            self.base_url,
            files={
                'file': (file_name, file_data)
            }
        )
        if response.ok:
            return response.json()
        else:
            raise Exception(f'Upload failed: {response.text}')

    def delete(self):
        response = requests.delete(self.base_url)
        if response.ok:
            return response.json()
        else:
            raise Exception(f'Delete failed: {response.text}')

class Tileset:
    def __init__(self, tileset_id, username, token):
        self.tileset_id = tileset_id
        self.username = username
        self.token = token
        self.base_url = f"https://api.mapbox.com/tilesets/v1/{username}.{tileset_id}"

    def create(self, recipe, name):
        url = f"{self.base_url}?access_token={self.token}"
        requestbody = {
            "recipe": recipe,
            "name": name
        }
        response = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(requestbody)
        )
        if response.ok:
            return response.json()
        else:
            raise Exception(f'Failed to create Tileset: {response.text}')

    def delete(self):
        url = f"{self.base_url}?access_token={self.token}"
        response = requests.delete(url)
        if response.ok:
            return response.json()
        else:
            raise Exception(f'Failed to delete Tileset: {response.text}')

    def publish(self):
        url_publish = f"{self.base_url}/publish?access_token={self.token}"
        response = requests.post(url_publish)
        if response.ok:
            return response.json()
        else:
            raise Exception(f'Failed to publish Tileset: {response.text}')

    def delete(self):
        url = f"{self.base_url}?access_token={self.token}"
        response = requests.delete(url)
        if response.ok:
            return response.json()
        else:
            raise Exception(f'Failed to delete Tileset: {response.text}')


'''
def get_s3_credentials():
    key = os.getenv('MB_KEY')
    url = "https://api.mapbox.com/uploads/v1/propsavant/credentials"
    query_params = {
        "access_token": key
    }
    response = requests.get(url, params=query_params)

    if response.status_code == 200:
        return response.json()
    return None


def model_to_mapbox_staging(model, s3_credentials, file_name='test'):
    try:
        s3_session = boto3.Session(
            aws_access_key_id=s3_credentials['accessKeyId'],
            aws_secret_access_key=s3_credentials['secretAccessKey'],
            aws_session_token=s3_credentials['sessionToken'],
            region_name='us-east-1'
        )
    except (BotoCoreError, NoCredentialsError) as e:
        print(f"Error creating S3 session: {e}")
        return None
    try:
        bucket_url_parts = s3_credentials['bucket'].replace('s3://', '').split('/')
        bucket_name = bucket_url_parts[0]
        object_key = '/'.join(bucket_url_parts[1:])
    except KeyError as e:
        print(f"Error extracting bucket details: {e}")
        return None
    try:
        geojson = serializers.serialize('geojson', model.objects.all())
    except Exception as e:
        print(f"Error serializing model data: {e}")
        return None


    s3_resource = s3_session.resource('s3')
    with tempfile.NamedTemporaryFile(suffix='.geojson', delete=False, mode='w') as f:
        json.dump(geojson, f)
        f.flush()
        try:
            response = s3_resource.Bucket(bucket_name).upload_file(f.name, file_name)
        except Exception as e:
            print(f"Error uploading file: {e}")
            response = None
    # Perform cleanup
    os.unlink(f.name)
    return response

'''

