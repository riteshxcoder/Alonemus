#
# Copyright (C) 2021-2022 by TheAloneteam@Github, < https://github.com/TheAloneTeam >.
#
# This file is part of < https://github.com/TheAloneTeam/AloneMusic > project,
# and is released under the "GNU v3.0 License Agreement".
# Please see < https://github.com/TheAloneTeam/AloneMusic/blob/master/LICENSE >
#
# All rights reserved.

import asyncio
import os
import re
from typing import Union

import yt_dlp
from py_yt import VideosSearch, Playlist
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

from AloneMusic import LOGGER
from AloneMusic.utils.formatters import time_to_seconds
from AloneMusic.utils.database import get_assistant_client

async def download_assistant(query: str, dl_type: str) -> str:
    ast = get_assistant_client()
    if not ast:
        return None

    bot = "MegaSaverBot"
    try:
        inline_results = await ast.get_inline_bot_results("vid", query)
        if not inline_results or not inline_results.results:
            return None

        inline_msg = await ast.send_inline_bot_result(
            chat_id="me",
            query_id=inline_results.query_id,
            result_id=inline_results.results[0].id
        )

        link = inline_msg.text if inline_msg.text else f"https://youtu.be/{inline_results.results[0].id}"
        sent_msg = await ast.send_message(bot, link)
        last_msg_id = sent_msg.id

        buttons_found = False
        target_keywords = ["MP3", "AUDIO"] if dl_type == "audio" else ["720", "720P", "HD"]

        for _ in range(15):
            await asyncio.sleep(2)
            async_history = ast.get_chat_history(bot, limit=3)
            async for m in async_history:
                if m and m.reply_markup and getattr(m.reply_markup, 'inline_keyboard', None) and m.id > last_msg_id:
                    for row in m.reply_markup.inline_keyboard:
                        for btn in row:
                            btn_text_upper = (getattr(btn, 'text', '') or '').upper()
                            if any(x in btn_text_upper for x in target_keywords):
                                if getattr(btn, 'callback_data', None):
                                    try:
                                        await ast.request_callback_answer(
                                            chat_id=bot,
                                            message_id=m.id,
                                            callback_data=btn.callback_data
                                        )
                                    except Exception:
                                        pass
                                buttons_found = True
                                last_msg_id = m.id
                                break
                        if buttons_found: break
                if buttons_found: break
            if buttons_found: break

        if not buttons_found:
            return None

        file_found = False
        for _ in range(30):
            await asyncio.sleep(2)
            async_history = ast.get_chat_history(bot, limit=3)
            async for m in async_history:
                has_media = m.audio if dl_type == "audio" else m.video
                if m and has_media and m.id > last_msg_id:
                    file_found = True
                    local_path = await ast.download_media(has_media)
                    if local_path and os.path.exists(local_path):
                        return local_path
                    break
            if file_found: break

        return None

    except Exception as e:
        LOGGER(__name__).error(f"Error in download_assistant: {e}")
        return None

async def download_song(link: str) -> str:
    return await download_assistant(link, "audio")

async def download_video(link: str) -> str:
    return await download_assistant(link, "video")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset : entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            else:
                return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        playlist = await Playlist.get(link)
        if playlist:
            videos = []
            for video in playlist["videos"][:limit]:
                try:
                    duration = video.get("duration")
                    if duration:
                        duration_sec = int(time_to_seconds(duration))
                    else:
                        duration_sec = 0
                    videos.append(
                        {
                            "vidid": video["id"],
                            "title": video.get("title", "Unknown"),
                            "duration_min": duration,
                            "duration_sec": duration_sec,
                            "thumbnail": (
                                video.get("thumbnails", [{}])[0]
                                .get("url", "")
                                .split("?")[0]
                                if video.get("thumbnails")
                                else ""
                            ),
                        }
                    )
                except:
                    continue
            return videos
        return None

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get("filesize"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
                except:
                    continue
        return formats_available, link

    async def slider(
        self, link: str, query_type: int, videoid: Union[bool, str] = None
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link

        try:
            if video or songvideo:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)

            if downloaded_file:
                return downloaded_file, True
            else:
                return None, False
        except Exception:
            return None, False
