# -*- coding: utf-8 -*-
# Copyright 2014 - 2016 OpenMarket Ltd
# Copyright 2018-2019 New Vector Ltd
# Copyright 2019 The Matrix.org Foundation C.I.C.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Contains functions for performing events on rooms."""

import logging
from synapse.handlers._base import BaseHandler
from synapse.api.errors import Codes, StoreError, SynapseError
from synapse.types import NewsID
from synapse.util import stringutils

logger = logging.getLogger(__name__)

id_server_scheme = "https://"

FIVE_MINUTES_IN_MS = 5 * 60 * 1000


class NewsCreationHandler(BaseHandler):

    def __init__(self, hs):
        super(NewsCreationHandler, self).__init__(hs)
        self.spam_checker = hs.get_spam_checker()
        self.event_creation_handler = hs.get_event_creation_handler()
        self.config = hs.config

    async def create_news(self, requester, config, ratelimit=False):  # Step 2 (Create room handler)
        user_id = requester.user.to_string()
        
        await self.auth.check_auth_blocking(user_id)

        if ratelimit:
            await self.ratelimit(requester)

        custom_whitespace = ['\t\n']
        if "room_id" in config:
            is_room_exist = await self.store.get_association_from_room_ids(config["room_id"])
            if not is_room_exist:
                raise SynapseError(400, "This room_id does not exist", Codes.ROOM_IN_USE)

        else:
            raise SynapseError(400, "Request body should contain 'room_id' param", 'NOT_CONTAIN_ROOM_ID')
        try:
            info = await self._generate_news_id(room_id=config.get('room_id'),
                                          news_content=config.get('news_content'))
            await self.event_creation_handler.create_and_send_nonmember_event(
                requester, {
                    "type": 'm.room.news',
                    "state_key": '',
                    "room_id": config.get('room_id'),
                    "sender": requester.user.to_string(),
                    "content": {
                        "news_id": info.get("news_id")
                    },
                }, ratelimit=False,
            )
            return info
        except Exception as e:
            raise SynapseError(400, f"{e} Problem with store poll")

    async def _generate_news_id(self, room_id, news_content):
        try:
            random_string = stringutils.random_string(18)
            gen_news_id = NewsID(random_string, room_id).to_string()
            if isinstance(gen_news_id, bytes):
                gen_news_id = gen_news_id.decode("utf-8")
            await self.store.store_news(
                news_id=gen_news_id,
                news_content=news_content,
                room_id=room_id
            )

            dict = {'news_id': gen_news_id}
            return dict
        except StoreError as e:
            logger.error("STORE ERROR", "", e)


class NewsModificationHandler(BaseHandler):

    def __init__(self, hs):
        super(NewsModificationHandler, self).__init__(hs)
        self.spam_checker = hs.get_spam_checker()
        self.event_creation_handler = hs.get_event_creation_handler()
        self.config = hs.config

    async def get_news_by_room_id(self, requester, room_id, ratelimit=False):  # Step 2 (Create room handler)
        """ Creates a new news article.

        Args:
            requester (synapse.types.Requester):
                The user who requested the pool creation.
            config (dict) : A dict of configuration options.
            ratelimit (bool): set to False to disable the rate limiter

            creator_join_profile (dict|None):
                Set to override the displayname and avatar for the creating
                user in this room. If unset, displayname and avatar will be
                derived from the user's profile. If set, should contain the
                values to go in the body of the 'join' event (typically
                `avatar_url` and/or `displayname`.

        Returns:
            Deferred[dict]:
                a dict containing the keys `room_id` and, if an alias was
                requested, `room_alias`.
        Raises:
            SynapseError if the room ID couldn't be stored, or something went
            horribly wrong.
            ResourceLimitError if server is blocked to some resource being
            exceeded
        """

        await self.auth.check_auth_blocking(room_id)
        ret_dict = {"news_info": []}
        info = await self.store.get_news_by_room_id(room_id)
        for elem in info:
            ret_dict["news_info"].append(elem)
        return ret_dict

    async def get_unread_news_by_room_id(self, requester, room_id, user_id, ratelimit=False):  # Step 2 (Create room handler)
        """ Creates a new news article.

        Args:
            requester (synapse.types.Requester):
                The user who requested the pool creation.
            config (dict) : A dict of configuration options.
            ratelimit (bool): set to False to disable the rate limiter

            creator_join_profile (dict|None):
                Set to override the displayname and avatar for the creating
                user in this room. If unset, displayname and avatar will be
                derived from the user's profile. If set, should contain the
                values to go in the body of the 'join' event (typically
                `avatar_url` and/or `displayname`.

        Returns:
            Deferred[dict]:
                a dict containing the keys `room_id` and, if an alias was
                requested, `room_alias`.
        Raises:
            SynapseError if the room ID couldn't be stored, or something went
            horribly wrong.
            ResourceLimitError if server is blocked to some resource being
            exceeded
        """

        await self.auth.check_auth_blocking(room_id)

        if ratelimit:
            await self.ratelimit(requester)
        ret_dict = {}
        info = await self.store.get_unread_news(room_id, user_id)
        ret_dict["news_info"] = info
        return ret_dict

    async def get_news_by_news_id(self, requester, news_id, ratelimit=False):  # Step 2 (Create room handler)
        """ Creates a new news article.

        Args:
            requester (synapse.types.Requester):
                The user who requested the pool creation.
            config (dict) : A dict of configuration options.
            ratelimit (bool): set to False to disable the rate limiter

            creator_join_profile (dict|None):
                Set to override the displayname and avatar for the creating
                user in this room. If unset, displayname and avatar will be
                derived from the user's profile. If set, should contain the
                values to go in the body of the 'join' event (typically
                `avatar_url` and/or `displayname`.

        Returns:
            Deferred[dict]:
                a dict containing the keys `room_id` and, if an alias was
                requested, `room_alias`.
        Raises:
            SynapseError if the room ID couldn't be stored, or something went
            horribly wrong.
            ResourceLimitError if server is blocked to some resource being
            exceeded
        """
        info = await self.store.get_news_by_news_id(news_id)
        return info

    async def set_news_read_marker(self, requester, config, ratelimit=False):  # Step 2 (Create room handler)
        """ Creates a new news article.

        Args:
            requester (synapse.types.Requester):
                The user who requested the pool creation.
            config (dict) : A dict of configuration options.
            ratelimit (bool): set to False to disable the rate limiter

            creator_join_profile (dict|None):
                Set to override the displayname and avatar for the creating
                user in this room. If unset, displayname and avatar will be
                derived from the user's profile. If set, should contain the
                values to go in the body of the 'join' event (typically
                `avatar_url` and/or `displayname`.

        Returns:
            Deferred[dict]:
                a dict containing the keys `room_id` and, if an alias was
                requested, `room_alias`.
        Raises:
            SynapseError if the room ID couldn't be stored, or something went
            horribly wrong.
            ResourceLimitError if server is blocked to some resource being
            exceeded
        """
        user_id = requester.user.to_string()

        await self.auth.check_auth_blocking(user_id)

        if ratelimit:
            await self.ratelimit(requester)
        if "news_id" in config:
            is_news_exist = await self.store.get_association_from_news_ids(config["news_id"])
            if not is_news_exist:
                raise SynapseError(400, "This news_id does not exist", "WRONG_NEWS_ID")
        if "room_id" in config:
            is_room_exist = await self.store.get_association_from_room_ids(config["room_id"])
            if not is_room_exist:
                raise SynapseError(400, "This room_id does not exist", Codes.ROOM_IN_USE)

        else:
            raise SynapseError(400, "Request body should contain 'news_id' param", 'NOT_CONTAIN_NEWS_ID')
        try:
            await self.store.set_read_marker(news_id=config.get('news_id'),
                                             user_id=config.get('user_id'),
                                             room_id=config.get('room_id'))

            return {"news_id": config.get('news_id'), "seen": True}
        except Exception as e:
            raise SynapseError(400, f"{e} Problem with store poll")