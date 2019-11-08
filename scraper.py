# -*- coding: utf-8 -*-
'''
This program was used to create the mood dataset.
It sources all music from YouTube videos, preferring '<artist_name> - Topic' channels and then 'VEVO' channels.
It has the capabilities to download songs from youtube by grabbing song names from acousticbrainz datasets,
songs in a youtube playlist, and from a CSV file
Author: Luis Gomez
        @whoislewys
        whoislewys@gmail.com
'''

import os
import re
import json
import csv
import requests
import youtube_dl
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set DEVELOPER_KEY to the API key value from the APIs & auth > Registered apps
# tab of
# https://cloud.google.com/console
# Please ensure that you have enabled the YouTube Data API for your project.
DEVELOPER_KEY = os.environ['GOOGLE_API_KEY']
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'


def youtube_search(youtube, yt_query):
    # Call the search.list method to retrieve results matching the specified
    # query term.
    response = youtube.search().list(
        q=yt_query,
        part='snippet',
        maxResults=10
    ).execute()
    return response


def get_abrainz_json(dataset_ID):
    # get an acousticbrainz dataset
    dataset_r = requests.get('http://acousticbrainz.org/api/v1/datasets/{}'.format(dataset_ID))
    return dataset_r.json()


def get_moods(abrainz_json):
    moods = []
    for counter, mood in enumerate(abrainz_json['classes']):
        mood = abrainz_json['classes'][counter]
        moods.append(mood)
    return moods


def get_song_IDs(songs):
    song_IDs = []
    for song in songs:
        song_IDs.append(song[0])
    return song_IDs


def get_youtube_query(json_r):
    # example search query: All-Star Smashmouth - Topic
    song_name = json_r['metadata']['tags']['title']
    artist = json_r['metadata']['tags']['artist']
    song_name = ''.join(song_name)
    artist = ''.join(artist)
    search_query = song_name + ' ' + artist + ' - Topic'
    return song_name, artist, search_query


def download_yt_song(URL, ydl_opts):
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([URL])


def get_yt_playlistItems(youtube, playlistId, pageToken):
    response = youtube.playlistItems().list(
        part='snippet, contentDetails',
        maxResults=50,
        playlistId=playlistId,
        pageToken=pageToken
    ).execute()
    return response


def get_topic_from_yt_response(song_name, artist, search_response, ydl_opts):
    # create regex patterns to check if the song you want actually has a video in your YouTube results
    song_name_pattern = re.compile('(?i)' + song_name)
    artist_pattern = re.compile('(?i)' + artist)
    topic_channel_pattern = re.compile('(?i)' + artist + ' - Topic')
    vevo_channel_pattern = re.compile('(?i)' + artist + 'VEVO')
    valid_song_index = -1
    song_found = True
    for counter, search_result in enumerate(search_response['items']):
        valid_song_index = -1
        song_found = True
        result_song_name = search_result['snippet']['title']
        result_channel = search_result['snippet']['channelTitle']

        try:
            search_result_ID = search_result['id']['videoId']
            search_result_URL = 'youtube.com/watch?v={}'.format(search_result_ID)
        except Exception as e:
            print('\nVideo id couldnt be found.')

        if song_name_pattern.search(result_song_name) is not None and topic_channel_pattern.search(result_channel) is not None:
            # if song name AND topic channel are found, download the song
            # TODO factor out search_result_ID and place it in a try catch
            print('\nDownloading {0} by {1}'.format(song_name, artist))
            try:
                download_yt_song(search_result_URL, ydl_opts)
            except Exception as e:
                print('something fucked up on {0} by {1}'.format(song_name, artist))
            break

        elif song_name_pattern.search(result_song_name) is not None and topic_channel_pattern.search(result_channel) is None:
            if artist_pattern.search(result_song_name) is not None:
                # if a song name IS found, but a 'topic' channel IS NOT found, download song and warn the user
                # search_result_ID = search_result['id']['videoId']
                # search_result_URL = 'youtube.com/watch?v={}'.format(search_result_ID)
                valid_song_index = counter
                break
            elif vevo_channel_pattern.search(result_song_name) is not None:
                # search_result_ID = search_result['id']['videoId']
                # search_result_URL = 'youtube.com/watch?v={}'.format(search_result_ID)
                valid_song_index = counter
                break

        elif song_name_pattern.search(result_song_name) is None:
            # if song name is never found, song_found flag will always be false. use it to warn the user
            song_found = False

    if song_found == False:
        print('\nSorry, song {0} by {1} not found.\n'.format(song_name, artist))
    if valid_song_index != -1:
        print('\nSong {0} found, but there was no \"topic\" channel. Downloading from {1}\n'.format(song_name,
                                                                                                    search_result_URL))
        try:
            download_yt_song(search_result_URL, ydl_opts)
        except Exception as e:
            print('something fucked up on {0} by {1}'.format(song_name, artist))


def download_acousticBrainz_songs(youtube, DATASET_ID, ydl_opts):
    abrainz_json = get_abrainz_json(DATASET_ID)
    moods = get_moods(abrainz_json)

    # iterate through moods, creating a new directory for the current mood if it doesn't exist
    for counter, mood in enumerate(moods):
        if os.path.exists(os.path.join(os.getcwd(), mood['name'])) == 0:
            os.makedirs(mood['name'], exist_ok=True)  # create dir for current mood
        ydl_opts['outtmpl'] = os.path.join(os.getcwd(), mood['name'],'%(title)s.%(ext)s')  # set ydl to dl to current mood dir
        ydl_opts['download_archive'] = os.path.join(os.getcwd(), mood['name'] + '_downloaded.txt')  # diff archive file for each mood

        # iterate through all song IDs in the current mood, make a youtube query for each one
        song_IDs = mood['recordings']

        for song_ID in song_IDs:
            abrainz_features_json = requests.get('http://acousticbrainz.org/api/v1/{}/low-level'.format(song_ID)).json()
            try:
                song_name, artist, yt_query = get_youtube_query(abrainz_features_json)
            except Exception as e:
                print('oh shit something fucked up on this songID {0} in the mood {1}'.format(song_ID, mood))

            search_response = youtube_search(youtube, yt_query)

            get_topic_from_yt_response(song_name, artist, search_response, ydl_opts)
            '''
            Should be able to delete this. Saving it here just in case
            # create regex patterns to check if the song you want actually has a video in your YouTube results
            song_name_pattern = re.compile('(?i)' + song_name)
            artist_pattern = re.compile('(?i)' + artist)
            topic_channel_pattern = re.compile('(?i)' + artist + ' - Topic')
            vevo_channel_pattern = re.compile('(?i)' + artist + 'VEVO')
            
            # search youtube using the query you just made (limited to top 10 results)
            
            
            # search through results for the song name and a 'topic' channel for the artist
            for counter, search_result in enumerate(search_response['items']):
                valid_song_index = -1
                song_found = True
                result_song_name = search_result['snippet']['title']
                result_channel = search_result['snippet']['channelTitle']
                try:
                    search_result_ID = search_result['id']['videoId']
                    search_result_URL = 'youtube.com/watch?v={}'.format(search_result_ID)
                except Exception as e:
                    print('\nVideo id couldnt be found.')
                if song_name_pattern.search(result_song_name) is not None and topic_channel_pattern.search(
                        result_channel) is not None:
                    # if song name AND topic channel are found, download the song
                    # TODO factor out search_result_ID and place it in a try catch
                    print('\nDownloading {0} by {1}'.format(song_name, artist))
                    try:
                        download_yt_song(search_result_URL, ydl_opts)
                    except Exception as e:
                        print('something fucked up on {0} by {1}'.format(song_name, artist))
                    break
                elif song_name_pattern.search(result_song_name) is not None and topic_channel_pattern.search(
                        result_channel) is None:
                    if artist_pattern.search(result_song_name) is not None:
                        # if a song name IS found, but a 'topic' channel IS NOT found, download song and warn the user
                        # search_result_ID = search_result['id']['videoId']
                        # search_result_URL = 'youtube.com/watch?v={}'.format(search_result_ID)
                        valid_song_index = counter
                        break
                    elif vevo_channel_pattern.search(result_song_name) is not None:
                        # search_result_ID = search_result['id']['videoId']
                        # search_result_URL = 'youtube.com/watch?v={}'.format(search_result_ID)
                        valid_song_index = counter
                        break
                elif song_name_pattern.search(result_song_name) is None:
                    # if song name is never found, song_found flag will always be false. use it to warn the user
                    song_found = False
            if song_found == False:
                print('\nSorry, song {0} by {1} not found.\n'.format(song_name, artist))
            if valid_song_index != -1:
                print('\nSong {0} found, but there was no \"topic\" channel. Downloading from {1}\n'.format(song_name,
                                                                                                            search_result_URL))
                try:
                    download_yt_song(search_result_URL, ydl_opts)
                except Exception as e:
                    print('something fucked up on {0} by {1}'.format(song_name, artist))
                    '''


def download_yt_playlist_songs(youtube, ydl_opts, mood, playlistId):
    # add all songIds to a list
    songIds = []
    nextPageToken = 'something'
    i = 0
    while nextPageToken is not None:
        if i == 0:
            nextPageToken = ''
        response = get_yt_playlistItems(youtube, playlistId, nextPageToken)
        ydl_opts['outtmpl'] = os.path.join(os.getcwd(), mood, '%(title)s.%(ext)s')  # set ydl to dl to current mood dir
        ydl_opts['download_archive'] = os.path.join(os.getcwd(), mood + '_downloaded.txt')  # diff archive file for each mood
        # TODO add all songs to a list
        for i, song in enumerate(response['items']):
            songIds.append(response['items'][i]['snippet']['resourceId']['videoId'])
        try:
            nextPageToken = response['nextPageToken']
        except Exception as e:
            print('No more new pages in playlist. Downloading songs now.')
            break
        i += 1

    # try downloading every song in the playlist
    for songId in songIds:
        try:
            download_yt_song(songId, ydl_opts)
        except Exception as e:
            print('Some error on song {}'.format(songId))


def download_songs_from_csv(csv_file, youtube, ydl_opts):
    '''
    HOW TO USE: DELETE FIRST ROW
    WHY DOES THIS FUNCTION EXIST? To Download spotify playlists
    Find a good spotify playlist, (e.g. Silk Sheets), follow the playlist.
    Go to playlistbuddy.com
    Select the playlist you just followed, in this case Silk Sheets.
    In the top right, click the CSV button.
    Open it in excel or similar software. Delete first row
    Okay credit where credit is due Spotify had some pretty indie shit on their silk sheets playlist so i had to download a lot manually
    added them all to the mood yt playlist but if i'm doing this again in the future, watch out,
    may have to manually download a lot of tracks (just make a list with all urls not downloadded and download in python console y=using download yt_song function)
    '''
    csv_filename = csv_file.split(os.sep)[-1:][0]
    ydl_opts['outtmpl'] = os.path.join(os.getcwd(), csv_filename, '%(title)s.%(ext)s')
    ydl_opts['download_archive'] = os.path.join(os.getcwd(), csv_filename + '_downloaded.txt')

    with open(csv_file) as csv_f:
        f = csv.reader(csv_f)
        for row in f:
            # expects song name in B column and artist in C column
            song_name = row[1]
            artist = '' + row[2]
            yt_query = song_name + artist + ' - Topic'
            yt_response = youtube_search(youtube, yt_query)
            get_topic_from_yt_response(song_name, artist, yt_response, ydl_opts)


if __name__ == '__main__':
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'download_archive': 'downloaded_songs.txt',
        'outtmpl': '',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
    }
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=DEVELOPER_KEY)

    # Uncomment whichever you want to use
    #
    # # Download YouTube Playlists #
    # playlistIds = {'Angry_yt': 'PLHu_1N0BiebrCFkIaZJXxPr8vnO7HKrLV',
    #                'Happy_yt': 'PLHu_1N0BiebqkMw35tE4iYJF5f--1ElvW',
    #                'Sad_yt': 'PLHu_1N0BiebouOrZ07RGdAN9CrhgK1wP6',
    #                'Sexy_yt': 'PLEZZiurJkE1RKkzegkfWeYWtG5zb6Zesc',
    #                }
    # for mood in playlistIds:
    #     download_yt_playlist_songs(youtube, ydl_opts, mood, playlistIds[mood])

    #
    # # Download AcousticBrainz Datasets #
    # Get more dataset ids from https://acousticbrainz.org/datasets/list
    # DATASET_ID = '1c8cc2be-73b8-4aff-9e07-793bf865a10a'
    # DATASET_ID = 'ce9ab690-c71c-43f7-a368-58efe24949c5'
    # download_acousticBrainz_songs(youtube, DATASET_ID, ydl_opts)
    #
    # # Download Songs from CSV exported from PlaylistBuddy (spotify to youtube playlist converter) #
    # note: download_songs_from_csv() searches for the '- topic' songs matching the song name in the CSV
    # make sure this scraper file is in the python sources directory w other files
    # place csvs in downloads folder for easy access
    # CSV_PATH = r'C:\Users\lewys\Downloads\Depression at 3 am.csv'
    # CSV_PATH = r'C:\Users\lewys\Downloads\Happy Pop.csv'
    # CSV_PATH = r'C:\Users\lewys\Downloads\Mad Mood.csv'
    CSV_PATH = r'C:\Users\lewys\PycharmProjects\mood_algorithm\mood-algorithm\girlontop.csv\The Girl on Top Playlist.csv'
    download_songs_from_csv(CSV_PATH, youtube, ydl_opts)
