import logging
from synapse.storage._base import SQLBaseStore

logger = logging.getLogger(__name__)


class NewsWorkerStore(SQLBaseStore):

    async def get_news_by_room_id(self, room_id):
        news = await self.db_pool.simple_select_list(
            table="news",
            keyvalues={"room_id": room_id},
            retcols=["news_id"],
            desc="get_user_news"
        )
        logger.info(f"NEWS - {news}")
        return news

    async def get_unread_news(self, room_id, user_id):
        read_news = await self.db_pool.simple_select_list(
            table="read_news",
            keyvalues={"room_id": room_id, "user_id": user_id},
            retcols=["news_id"],
            desc="get_user_news"
        )
        read_news_ids = [elem.get("news_id") for elem in read_news]
        news = await self.db_pool.simple_select_list(
            table="news",
            keyvalues={"room_id": room_id},
            retcols=["news_id"],
            desc="get_user_news"
        )
        news_ids = [article.get("news_id") for article in news]
        ret_list = []
        for n_id in news_ids:
            if n_id not in read_news_ids:
                ret_list.append({"news_id": n_id, "seen": False})
        return ret_list

    async def get_news_by_news_id(self, news_id):
        news = await self.db_pool.simple_select_one(
            table="news",
            keyvalues={
                "news_id": news_id
            },
            retcols=("news_id", "news_content", "active"),
            desc="get_news_by_news_id",
            allow_none=True
        )
        return news

    async def set_read_marker(self, user_id, news_id, room_id):
        def set_read_marker_txn(txn):
            self.db_pool.simple_insert_txn(
                txn,
                "read_news",
                {
                    "user_id": user_id,
                    "news_id": news_id,
                    "room_id": room_id
                },
            )

        await self.db_pool.runInteraction("set_read_marker_txn", set_read_marker_txn)

    async def store_news(self, news_content, room_id, news_id):
        def add_news_txn(txn):
            self.db_pool.simple_insert_txn(
                txn,
                "news",
                {
                    "news_id": news_id,
                    "news_content": news_content,
                    "room_id": room_id,
                    "active": True
                },
            )

        await self.db_pool.runInteraction("add_news_txn", add_news_txn)
