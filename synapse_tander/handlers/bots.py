import logging
import uuid
from synapse.api.errors import SynapseError
from synapse.handlers._base import BaseHandler

logger = logging.getLogger(__name__)


class BotMenuHandler(BaseHandler):

    def __init__(self, hs):
        super(BotMenuHandler, self).__init__(hs)
        self.event_creation_handler = hs.get_event_creation_handler()

    async def get_root_menu(self, requester, room_id, ratelimit=True):
        bot_id = await self.store.get_bot_by_room(room_id)
        if bot_id:
            bot_data = await self.store.get_root_bot_menu(bot_id.get('bot_user_id'))
            return bot_data
        else:
            return None

    async def get_menu_buttons(self, requester, menu_id, ratelimit=True):
        bot_data = await self.store.get_menu_buttons(menu_id)
        return {"data": bot_data}

    async def get_full_menu_buttons(self, requester, menu_id, ratelimit=True):
        bot_data = await self.store.get_menu_buttons(menu_id)
        result_dict = []
        for button_dict in bot_data:
            button_id = button_dict.get('button_id')
            button_action_dict = await self.get_button_action(None, button_dict.get('button_id'))
            result_dict.append({'button_id': button_id,
                                'button_action': {'event_type': button_action_dict.get('event_type'),
                                                  'event_content': button_action_dict.get('event_content')}})
        return {"data": result_dict}

    async def get_button_action(self, requester, button_id, ratelimit=True):
        bot_data = await self.store.get_button_action(button_id)
        if not bot_data:
            raise SynapseError(400, f'Button {button_id} does not provide any actions')
        return bot_data

    async def set_root_menu(self, requester, menu_id, ratelimit=True):
        if not menu_id:
            raise SynapseError(400, f'Required parameters are [menu_id]')
        menu_exist = await self.store.get_menu_id_association(menu_id)
        bot_id = menu_id.split('|')[-1]
        room_root_menu = await self.store.get_root_bot_menu(bot_id)
        logger.info(f'ROOM ROOT MENU {room_root_menu}')

        if not menu_exist:
            raise SynapseError(400, f'Menu with id {menu_id} does not exist')

        if room_root_menu is None:
            await self.store.set_root_bot_menu(menu_id)

        if room_root_menu:
            await self.store.uncheck_menu_as_root(menu_id)
            await self.store.set_root_bot_menu(menu_id)

        return {'menu_id': menu_id, 'bot_user_ud': bot_id, 'root': True}

    async def add_menu_to_bot(self, requester, bot_id, ratelimit=True):
        if not bot_id:
            raise SynapseError(400, f'Required parameters are [bot_id]')
        is_bot = await self.store.check_user_as_bot(bot_id)
        if not is_bot:
            raise SynapseError(400, f'Bot with id {bot_id} does not exist')
        created_menu_id = f'menu_{str(uuid.uuid4().hex)[:8]}|{bot_id}'
        await self.store.add_menu_to_bot(bot_id, created_menu_id)
        return {'bot_id': bot_id, 'menu_id': created_menu_id, 'root': False}

    async def add_button_to_menu(self, requester, menu_id, config, ratelimit=True):
        menu_exist = await self.store.get_menu_id_association(menu_id)
        if not menu_exist:
            raise SynapseError(400, f'Menu with id {menu_id} does not exist')
        event_type = config.get('event_type')
        event_content = config.get('event_content')
        button_text = config.get('button_text')
        if not event_type or not event_content:
            raise SynapseError(400, f'Required parameters are [event_type, event_content, button_text]')
        if event_type not in ['redirect', 'message']:
            raise SynapseError(400, f'Supported event types [redirect, message]')
        if event_type == 'redirect':
            redirected_menu_id = event_content
            menu_exist = await self.store.get_menu_id_association(redirected_menu_id)
            if not menu_exist:
                raise SynapseError(400, f'Redirected menu with id {menu_id} does not exist')
        button_id = f'{str(uuid.uuid4())[:4]}|{menu_id}'
        await self.store.add_button_to_menu(menu_id=menu_id, button_id=button_id, button_text=button_text)
        await self.store.add_button_action(button_id=button_id, event_type=event_type, event_content=event_content)
        return {'button_id': button_id, 'button_text': button_text, 'action': {'event_type': event_type,
                                                                               'event_content': event_content}}

    async def make_bot_action(self, requester, button_id, room_id, ratelimit=True):
        button_action = await self.store.get_button_action(button_id)
        if not button_action:
            raise SynapseError(400, f'Button {button_id} does not provide any actions')
        event_type = button_action.get('event_type')
        event_content = button_action.get('event_content')
        if event_type != 'message':
            raise SynapseError(400, f'Button {button_id} does not provide \'message\' event')
        await self.event_creation_handler.create_and_send_nonmember_event(
            requester, {
                "type": 'm.room.message',
                "room_id": room_id,
                "sender": requester.user.to_string(),
                "content": {
                    "msgtype": "m.text",
                    "body": event_content,
                    "sender_ip": "127.0.0.1",
                }
            }, ratelimit=False,
        )
        return {'button_id': button_id, 'event_status': 'sent'}

    async def bot_add_or_create_room(self, requester, room_id, invite_list):
        for user_id in invite_list:
            is_bot = await self.store.check_user_as_bot(user_id)
            logger.info(f'IS USER BOT - {is_bot}')
            if is_bot:
                is_room_assigned_to_bot = await self.store.get_bot_room_association(room_id, user_id)
                logger.info(f'IS USER ASSUGNED TO ROOM - {is_room_assigned_to_bot}')
                if not is_room_assigned_to_bot:
                    await self.event_creation_handler.create_and_send_nonmember_event(
                        requester, {
                            "type": 'm.room.invite_bot',
                            "room_id": room_id,
                            "sender": requester.user.to_string(),
                            "state_key": "",
                            "content": {
                                "bot_user_id": user_id,
                                "sender_ip": "127.0.0.1"
                            }
                        }, ratelimit=False,
                    )
                    await self.store.add_room_to_bot(user_id, room_id)
