import requests

response = requests.get(
    'https://{0}:8443'.format('rc1d-av86cgpnu0cm7m8j.mdb.yandexcloud.net'),
    params={
        'query': 'SELECT version()',
    },
    headers={
        'X-ClickHouse-User': 'admin',
        'X-ClickHouse-Key': '12345678',
    },
    verify='/usr/local/share/ca-certificates/Yandex/RootCA.crt'
)

print(response.text)
response.raise_for_status()