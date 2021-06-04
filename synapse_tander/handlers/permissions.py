import logging
from synapse.handlers._base import BaseHandler
logger = logging.getLogger(__name__)


class PermissionsListHandler(BaseHandler):

    def __init__(self, hs):
        super(PermissionsListHandler, self).__init__(hs)

    async def get_permissions(self, requester, ratelimit=False):
        user_id = requester.user.to_string()
        logger.info(f"GET PERMS FOR USER {user_id}")
        if ratelimit:
            await self.ratelimit(requester)
        permissions = await self.store.get_all_user_permissions(user_id)
        return {"permissions": permissions}