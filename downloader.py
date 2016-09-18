import configparser
import os
import requests
import sys
from typing import List

from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError


def __create_client() -> ImgurClient:
    config = configparser.ConfigParser()
    config.read('credentials.ini')
    client_id = config.get('client', 'id')
    client_secret = config.get('client', 'secret')
    return ImgurClient(client_id, client_secret)


def __get_image_links(album_id: str) -> List[str]:
    client = __create_client()
    images = client.get_album_images(album_id)
    print('Found {} images in album'.format(len(images)))

    result = []
    for img in images:
        link = img.mp4 if hasattr(img, 'mp4') else img.link
        result.append(link.replace('http:', 'https:'))
    return result


def __save_images(images: List[str]):
    os.makedirs('images', exist_ok=True)
    total_attempted = len(images)
    total_complete = 0
    total_bytes = 0
    for link in images:
        local_path = 'images/' + os.path.basename(link)
        if os.path.isfile(local_path):
            print('Already downloaded: ' + link)
            total_attempted -= 1
            continue

        print('Downloading ' + link + ' ... ', end='')
        try:
            res = requests.get(link)
            res.raise_for_status()
            with open(local_path, 'wb') as file:
                byte_size = 0
                for chunk in res.iter_content(100000):
                    byte_size += file.write(chunk)
            print('success! Size: {}MB'.format(round(byte_size / 1048576.0, 2)))
            total_bytes += byte_size
            total_complete += 1
        except Exception as ex:
            print('failed! Reason: {}'.format(ex))
    print('Successfully downloaded {}/{} images ({}MB total)'.format(
        total_complete, total_attempted, round(total_bytes / 1048576.0, 2)))


def download_album(album_id: str):
    print("Attempting to download album '{}'".format(album_id))
    try:
        __save_images(__get_image_links(album_id))
    except ImgurClientError:
        print("No such album '{}'".format(arg))


if __name__ == '__main__':
    args = sys.argv[1:]
    if args:
        for arg in args:
            download_album(arg)
    else:
        download_album(input('Please pass in an album id: '))
