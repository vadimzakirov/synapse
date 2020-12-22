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
from synapse.types import PollID, StreamToken, UserID
from synapse.util import stringutils

logger = logging.getLogger(__name__)

id_server_scheme = "https://"

FIVE_MINUTES_IN_MS = 5 * 60 * 1000


class PollCreationHandler(BaseHandler):

    def __init__(self, hs):
        super(PollCreationHandler, self).__init__(hs)
        self.spam_checker = hs.get_spam_checker()
        self.event_creation_handler = hs.get_event_creation_handler()
        self.config = hs.config

    async def create_poll(self, requester, config, ratelimit=True):  # Step 2 (Create room handler)
        """ Creates a new pool.

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

        custom_whitespace = ['\t\n']
        if "poll_alias_name" in config:
            is_room_exist = await self.store.get_association_from_room_ids(config["room_id"])
            if not is_room_exist:
                raise SynapseError(400, "This room_id does not exist", Codes.ROOM_IN_USE)

        else:
            poll_alias = None
        try:
            info = await self._generate_poll_id(creator_id=user_id,
                                                poll_alias=config["poll_alias_name"],
                                                room_id=config["room_id"])

        except Exception as e:
            raise SynapseError(400, "Problem with store poll")

        if "options" in config:
            for option in config["options"]:
                for wchar in custom_whitespace:
                    if wchar in option:
                        raise SynapseError(400, "Invalid characters in poll's option")

            data = {
                "info": info,
                "options": []
            }
            num = 1
            for option in config["options"]:
                data["options"].append(await self._add_option(poll_id=info["poll_id"],
                                                              option_name=option,
                                                              option_number=num
                                                              ))
                num += 1
            (
                _,
                last_stream_id,
            ) = await self.event_creation_handler.create_and_send_nonmember_event(
                requester,
                {
                    "type": 'm.room.poll',
                    "room_id": config.get('room_id'),
                    "sender": user_id,
                    "state_key": "",
                    "content": {"poll_id": data.get("poll_id")}
                },
                ratelimit=False,
            )
            return data
        else:
            raise SynapseError(400, "No options specified")

    async def _generate_poll_id(self, creator_id, poll_alias, room_id):
        try:
            random_string = stringutils.random_string(18)
            gen_poll_id = PollID(random_string, room_id).to_string()
            if isinstance(gen_poll_id, bytes):
                gen_poll_id = gen_poll_id.decode("utf-8")
            await self.store.store_poll(
                poll_id=gen_poll_id,
                poll_creator_user_id=creator_id,
                poll_alias=poll_alias,
                room_id=room_id
            )
            dict = {
                'poll_id': gen_poll_id,
                'poll_creator_user_id': creator_id,
                'poll_alias': poll_alias,
                'room_id': room_id
            }
            return dict
        except StoreError as e:
            logger.error("STORE ERROR", "", e)

    async def _add_option(self, poll_id, option_name, option_number):
        try:
            if isinstance(poll_id, bytes):
                poll_id = poll_id.decode("utf-8")
            await self.store.add_option_to_poll(
                option_number=option_number,
                poll_id=poll_id,
                option_name=option_name,
            )

            data = {
                "option_number": option_number,
                "name": option_name,
            }

            return data

        except StoreError as e:
            logger.error("STORE ERROR", "", e)


class PollModificationHandler(BaseHandler):

    def __init__(self, hs):
        super(PollModificationHandler, self).__init__(hs)
        self.spam_checker = hs.get_spam_checker()
        self.event_creation_handler = hs.get_event_creation_handler()
        self.config = hs.config

    async def increment_option_in_poll(self, requester, config, ratelimit=True):  # Step 2 (Create room handler)
        """ Creates a new pool.

        Args:
            requester (synapse.types.Requester):
                The user who requested the pool creation.
            config (dict) : A dict of configuration options.
            {
                "poll_id" : String
                "option_number": String/Integer
            }
            ratelimit (bool): set to False to disable the rate limiter


            SynapseError if the room ID couldn't be stored, or something went
            horribly wrong.
            ResourceLimitError if server is blocked to some resource being
            exceeded
        """
        user_id = requester.user.to_string()
        if ratelimit:
            await self.ratelimit(requester)

        if "option_number" in config:
            is_poll_exist = await self.store.get_association_from_poll_ids(config["poll_id"])
            is_option_exist_in_poll = await self.store.get_association_from_poll_options(
                poll_id=config["poll_id"],
                option_number=config["option_number"]
            )
            if not is_poll_exist:
                raise SynapseError(400, "This poll_id does not exist", "POLL_ID_ERROR")
            if not is_option_exist_in_poll:
                raise SynapseError(400, f"This option_number does not exist in poll_id: {config['poll_id']}",
                                   "POLL_ERROR")
        else:
            raise SynapseError(400, "No options were specified")
        try:
            user_voted = await self._check_user_voted(config["poll_id"], user_id)
            if user_voted:
                raise SynapseError(400, "User has already voted")
            new_count = await self._increment_option(config["option_number"], config["poll_id"], user_id)
        except StoreError as e:
            raise SynapseError(400, "Invalid option_number or poll_id")
        data = {"info": "Option incremented successfully", "poll_id": config["poll_id"],
                "number": config["option_number"],
                "count": new_count}
        return data

    async def finish_poll(self, requester, config, ratelimit=True):  # Step 2 (Create room handler)
        data = {}
        if ratelimit:
            await self.ratelimit(requester)

        if "poll_id" in config:
            is_poll_exist = await self.store.get_association_from_poll_ids(config["poll_id"])
            if not is_poll_exist:
                raise SynapseError(400, "This poll_id does not exist", "POLL_ID_ERROR")
        else:
            raise SynapseError(400, "Poll_id didn't specified")
        await self._finish_poll(config["poll_id"])
        polls_options_info = await self.store.get_polls_options(config["poll_id"])
        polls_info = await self.store.get_one_polls_info(config["poll_id"])
        for poll in polls_info:
            data = {
                "poll_id": config["poll_id"],
                "poll_active": poll["active"],
                "poll_alias_name": poll["poll_alias"],
                "creator": poll["poll_creator_user_id"],
                "options": polls_options_info

            }
        return data

    async def _increment_option(self, option_number, poll_id, user_id):

        if isinstance(poll_id, bytes):
            poll_id = poll_id.decode("utf-8")

        option_new_count = await self.store.increment_option_in_poll(
            option_number=option_number,
            poll_id=poll_id
        )
        await self.store.add_voted_user(
            option_number=option_number,
            poll_id=poll_id,
            user_id=user_id
        )
        return option_new_count

    async def _check_user_voted(self, poll_id, user_id):

        if isinstance(poll_id, bytes):
            poll_id = poll_id.decode("utf-8")

        option_number = await self.store.is_user_voted(
            poll_id=poll_id,
            user_id=user_id
        )
        return option_number

    async def _finish_poll(self, poll_id):

        if isinstance(poll_id, bytes):
            poll_id = poll_id.decode("utf-8")
        await self.store.finish_poll(
            poll_id=poll_id
        )


class GetPollInfoHandler(BaseHandler):

    def __init__(self, hs):
        super(GetPollInfoHandler, self).__init__(hs)
        self.spam_checker = hs.get_spam_checker()
        self.event_creation_handler = hs.get_event_creation_handler()
        self.config = hs.config

    async def get_polls_from_room_id(self, requester, room_id, ratelimit=True):

        user_id = requester.user.to_string()
        if ratelimit:
            await self.ratelimit(requester)

        try:
            is_room_exist = await self.store.get_association_from_room_ids(room_id)
        except Exception as e:
            raise SynapseError(400, "Error with room_id check")

        if not is_room_exist:
            raise SynapseError(400, "This room_id does not exist")

        try:
            polls_info = await self.store.get_polls_info(room_id)
            polls = []
            for poll in polls_info:
                creator = poll["poll_creator_user_id"]
                options = await self.store.get_polls_options(poll["poll_id"])
                is_voted = await self.store.is_user_voted(poll["poll_id"], user_id)
                polls.append({
                    "poll_id": poll["poll_id"],
                    "poll_alias": poll["poll_alias"],
                    "options": options,
                    "creator": creator,
                    "poll_active": poll["active"],
                    "voted": is_voted
                })
            data = {
                "room_id": room_id,
                "info": polls
            }

            return data
        except Exception as e:
            raise SynapseError(400, "This room does not have polls")
