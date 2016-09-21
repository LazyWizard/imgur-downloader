import configparser
import os
import requests
import sys
from typing import List

from imgurpython import ImgurClient
from imgurpython.helpers.error import ImgurClientError


def __create_client() -> ImgurClient:
    #  Set up ImgurClient with our OAuth2 credentials, obtained here: https://api.imgur.com/oauth2/addclient
    config = configparser.ConfigParser()
    config.read('credentials.ini')
    client_id = config.get('client', 'id')
    client_secret = config.get('client', 'secret')
    return ImgurClient(client_id, client_secret)
__client = __create_client()


def __get_image_links(album_id: str) -> List[str]:
    images = __client.get_album_images(album_id)
    print('Found {} images in album'.format(len(images)))

    result = []
    for img in images:
        #  Large GIFs will have an MP4 version (.gifv) as well, we should prefer these as they are much smaller
        link = img.mp4 if hasattr(img, 'mp4') else img.link
        result.append(link.replace('http:', 'https:'))
    return result


def __save_images(folder_name: str, images: List[str]):
    path = 'images/' + folder_name
    os.makedirs(path, exist_ok=True)
    total_attempted = total_complete = total_bytes = 0
    for link in images:
        #  Don't download the image if we already have a copy
        local_path = path + '/' + os.path.basename(link)
        if os.path.isfile(local_path):
            print('Already downloaded: ' + link)
            continue

        #  Download image and save to disk, save total bytes downloaded for later reporting
        print('Downloading ' + link + ' ... ', end='')
        total_attempted += 1
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
    """
    Downloads all images in a public album to its own directory, found under images/<album id>/.

    Args:
        album_id: the ID of the album, the part after https://imgur.com/a/
    """
    print("Attempting to download album '{}'".format(album_id))
    try:
        __save_images(album_id, __get_image_links(album_id))
    except ImgurClientError:
        print("No such album '{}'!".format(album_id))


def download_account(account_name: str):
    """
    Downloads all public albums of an account. Each album is downloaded to its own directory as if download_album
    had been called on each one separately (which is indeed what happens under the hood).


    Args:
        account_name: the ID of the account, found by clicking on a username and taking the part of the URL
        before imgur.com
    """
    print("Attempting to download account '{}'".format(account_name))
    try:
        album_ids = __client.get_account_album_ids(account_name)
        print("Found {} public albums for account '{}'".format(len(album_ids), account_name))
        for album_id in album_ids:
            download_album(album_id)
    except ImgurClientError:
        print("No such public account '{}'! Attempting as album...".format(account_name))
        download_album(account_name)


if __name__ == '__main__':
    args = sys.argv[1:]
    #  If command line arguments are passed in, assume it's a list of album IDs
    if args:
        for arg in args:
            download_album(arg)
    #  Otherwise prompt the user for input
    else:
        download_account(input('Please pass in an account name or album id: '))
