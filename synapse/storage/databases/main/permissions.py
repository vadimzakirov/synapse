import logging
from synapse.storage._base import SQLBaseStore

logger = logging.getLogger(__name__)


class AccessWorkerStore(SQLBaseStore):

    async def is_method_allow_for_user_none_room(self, api_path, method, user_id):
        individual_check = await self.db_pool.simple_select_one(
            table="permissions",
            keyvalues={"path": api_path,
                       "entity": user_id,
                       "method": method
                       },
            retcols=("allowed", "method"),
            desc="get_user_permission",
            allow_none=True,
        )
        if individual_check is None:
            groups = await self.get_groups_for_user(user_id)
            for group in groups:
                group_check = await self.db_pool.simple_select_one(
                    table="permissions",
                    keyvalues={
                        "path": api_path,
                        "entity": group.get('name'),
                        "method": method
                    },
                    retcols=("allowed", "method"),
                    desc="get_user_permission",
                    allow_none=True,
                )
                if group_check is not None:
                    if not group_check.get("allowed"):
                        return False
            return True
        else:
            return individual_check.get("allowed")

    async def get_groups_for_user(self, user_id):
        groups = await self.db_pool.simple_select_list(
            table="permission_groups",
            keyvalues={"user_id": user_id},
            retcols=["name"],
            desc="get_user_groups"
        )
        return groups

    async def add_permission_for_user_none_room(self, api_path, method, entity):
        def add_permission_txn(txn):
            self.db_pool.simple_insert_txn(
                txn,
                "permissions",
                {
                    "path": api_path,
                    "method": method,
                    "entity": entity,
                    "allowed": False
                },
            )

        await self.db_pool.runInteraction("add_permission_txn", add_permission_txn)

    async def add_user_in_group(self, user_id, group_name):
        def add_group_txn(txn):
            self.db_pool.simple_insert_txn(
                txn,
                "permission_groups",
                {
                    "name": group_name,
                    "user_id": user_id,
                },
            )

        await self.db_pool.runInteraction("add_group_txn", add_group_txn)

    async def get_all_user_permissions(self, user_id):
        permissions = []
        groups = await self.db_pool.simple_select_list(
            table="permission_groups",
            keyvalues={"user_id": user_id},
            retcols=["name"],
            desc="get_user_groups"
        )
        logger.info(f"USER GROUPS - {groups}")
        if groups:
            for group in groups:
                group_check = await self.db_pool.simple_select_one(
                    table="permissions",
                    keyvalues={
                        "entity": group.get("name"),
                    },
                    retcols=("method", "path", "allowed"),
                    desc="get_user_permission",
                    allow_none=True,
                )
                logger.info(f"GROUP CHECK - {group_check}")
                if group_check:
                    group_allow = group_check.get("allowed")
                    ind_allow = await self.is_method_allow_for_user_none_room(group_check.get("path"),
                                                                        group_check.get("method"),
                                                                        user_id)
                    logger.info(f"GROUP ALLOW - {group_allow}")
                    logger.info(f"IND ALLOW - {ind_allow}")
                    if (not group_allow and not ind_allow) or (group_allow and not ind_allow):
                        permissions.append({
                            "method": group_check.get("method"),
                            "path": group_check.get("path")
                        })
                        logger.info(f"SUCCESS PERMISSIONS APPEND - {permissions}")
                else:
                    ind_check = await self.db_pool.simple_select_list(
                        table="permissions",
                        keyvalues={"entity": user_id},
                        retcols=["path", "method", "allowed"],
                        desc="get_user_groups"
                    )
                    logger.info(f"IF NOT GROUP CHECK - IND CHECK - {ind_check}")
                    for perm in ind_check:
                        if not perm.get("allowed"):
                            permissions.append({
                                "method": perm.get("method"),
                                "path": perm.get("path")
                            })
                    logger.info(f"IF NOT GROUP CHECK - PERMS - {permissions}")
        else:
            ind_check = await self.db_pool.simple_select_list(
                table="permissions",
                keyvalues={"entity": user_id},
                retcols=["path", "method", "allowed"],
                desc="get_user_groups"
            )
            logger.info(f"IND CHECK NULL GROUP - {ind_check}")
            for perm in ind_check:
                if not perm.get("allowed"):
                    permissions.append({
                        "method": perm.get("method"),
                        "path": perm.get("path")
                    })
            logger.info(f"IND CHECK NULL GROUP - PERMS - {permissions}")
        return permissions
