import configparser
import os
import requests
import sys
from collections import namedtuple
from typing import List

from imgurpython import ImgurClient
from imgurpython.imgur.models.image import Image
from imgurpython.helpers.error import ImgurClientError


def __create_client() -> ImgurClient:
    # Set up ImgurClient with our OAuth2 credentials, obtained here: https://api.imgur.com/oauth2/addclient
    config = configparser.ConfigParser()
    config.read('credentials.ini')
    client_id = config.get('client', 'id')
    client_secret = config.get('client', 'secret')
    return ImgurClient(client_id, client_secret)
__client = __create_client()


def __get_image_links(images: List[Image]) -> List[str]:
    print('Found {} images in album'.format(len(images)))

    result = []
    for image in images:
        # Large GIFs will have an MP4 version (.gifv) as well; we prefer these as they are much smaller than GIFs
        link = image.mp4 if hasattr(image, 'mp4') else image.link
        result.append(link.replace('http:', 'https:'))
    return result


# Returned by various functions to pass along the results of a download attempt
Result = namedtuple('Result', 'downloaded, failed, skipped, total_bytes')


def __save_images(folder_name: str, images: List[str]) -> Result:
    path = 'images/' + folder_name
    os.makedirs(path, exist_ok=True)
    num_downloaded = num_failed = num_skipped = total_bytes = 0
    for link in images:
        # Don't download the image if we already have a copy
        local_path = path + '/' + os.path.basename(link)
        if os.path.isfile(local_path):
            print('Already downloaded: ' + link)
            num_skipped += 1
            continue

        # Download image and save to disk; save total bytes downloaded for later reporting
        print('Downloading ' + link + ' ... ', flush=True, end='')
        try:
            res = requests.get(link)
            res.raise_for_status()
            with open(local_path, 'wb') as file:
                byte_size = 0
                for chunk in res.iter_content(100000):
                    byte_size += file.write(chunk)
            print('success! Size: {}MB'.format(round(byte_size / 1048576.0, 2)))
            total_bytes += byte_size
            num_downloaded += 1
        except Exception as ex:
            print('failed! Reason: {}'.format(ex))
            num_failed += 1
    print('Successfully downloaded {}/{} images, skipped {} (downloaded {}MB total)'.format(
        num_downloaded, num_downloaded + num_failed, num_skipped, round(total_bytes / 1048576.0, 2)))
    return Result(num_downloaded, num_failed, num_skipped, total_bytes)


def download_album(album_id: str) -> Result:
    """
    Downloads all images in a public album to its own directory, found under "images/<username> - <album id> -
    <album title>/". Previously downloaded images will be ignored, and in the case of large GIFs the downloader will
    try to grab an MP4 version first.

    Args:
        album_id: the ID of the album, the part after https://imgur.com/a/
    Returns:
        A Result tuple containing the number of images downloaded, the number of images that failed to download, the
        number of images skipped because a local copy already existed, and the total amount of bytes downloaded.
        These values can be retrieved with result.downloaded, result.failed, result.skipped, and result.total_bytes
        respectively.
    """
    print("Attempting to download album '{}'".format(album_id))
    try:
        album = __client.get_album(album_id)
        author = album.account_url or "Anonymous"
        title = album.title or "Untitled"
        return __save_images('{} - {} - {}'.format(author, album.id, title),
                             __get_image_links([Image(image) for image in album.images]))
    except ImgurClientError:
        print("No such album '{}'!".format(album_id))


def download_account(account_name: str) -> Result:
    """
    Downloads all public albums of an account. Each album is downloaded to its own directory as if download_album
    had been called on each one separately (which is indeed what happens under the hood). The program prompts the user
    for each album separately, allowing them to choose which albums should be downloaded.

    Args:
        account_name: the ID of the account, found by clicking on a username and taking the part of the URL
        before imgur.com
    Returns:
        A Result tuple containing the number of images downloaded, the number of images that failed to download, the
        number of images skipped because a local copy already existed, and the total amount of bytes downloaded.
        These values can be retrieved with result.downloaded, result.failed, result.skipped, and result.total_bytes
        respectively.
    """
    print("Attempting to download account '{}'".format(account_name))
    try:
        # Note: albums returned via get_account_albums don't include images, so we'll have to retrieve that data later
        albums = __client.get_account_albums(account_name)
        num_downloaded = num_failed = num_skipped = total_bytes = 0
        print("Found {} public albums for account '{}'".format(len(albums), account_name))

        # Prompt on which of an account's albums to download
        to_download = []
        for i, album in enumerate(albums):
            prompt = input("Download album {}/{}; '{}' (id: '{}'; {} images)? y/n "
                           .format(i + 1, len(albums), album.title, album.id, album.images_count))
            if str.lower(prompt) == 'y':
                to_download.append(album)

        # Save list of downloaded albums so they can be passed in as command line arguments if something goes wrong
        with open('last_downloaded', 'wt') as file:
            file.write(" ".join([album.id for album in to_download]))

        # Download each individual album and add its download attempt results to the global stats
        print('Downloading {} albums, skipping {}'.format(len(to_download), len(albums) - len(to_download)))
        for album in to_download:
            result = download_album(album.id)
            num_downloaded += result.downloaded
            num_failed += result.failed
            num_skipped += result.skipped
            total_bytes += result.total_bytes
        print('Parsed {} albums. Successfully downloaded {}/{} images, skipped {} (downloaded {}MB total)'.format(
            len(to_download), num_downloaded, num_downloaded + num_failed,
            num_skipped, round(total_bytes / 1048576.0, 2)))
        return Result(num_downloaded, num_downloaded, num_skipped, total_bytes)
    except ImgurClientError:
        print("No such public account '{}'! Reattempting as album...".format(account_name))
        return download_album(account_name)


if __name__ == '__main__':
    args = sys.argv[1:]  # Exclude argv[0], which is the script name
    # If command line arguments are passed in, assume it's a list of album IDs
    if args:
        for arg in set(args):
            download_album(arg)
    # Otherwise prompt the user for input, and allow downloading entire accounts
    else:
        download_account(input('Please pass in an account name or album id: '))
