# +++ Modified By [telegram username: @Codeflix_Bots

import asyncio
from datetime import datetime
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import BotCommand
from config import API_HASH, APP_ID, LOGGER, TG_BOT_TOKEN, TG_BOT_WORKERS, PORT, OWNER_ID
from plugins import web_server
import pyrogram.utils
from aiohttp import web

pyrogram.utils.MIN_CHANNEL_ID = -1009147483647

name = "Links Sharing Started"

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="LinkShareBot",
            api_hash=API_HASH,
            api_id=APP_ID,
            plugins={"root": "plugins"},
            workers=TG_BOT_WORKERS,
            bot_token=TG_BOT_TOKEN,
        )
        self.LOGGER = LOGGER

    async def start(self, *args, **kwargs):
        await super().start()
        usr_bot_me = await self.get_me()
        self.username = usr_bot_me.username
        self.uptime = datetime.now()

        # ✅ AUTO SET BOT COMMANDS (Stylish)
        commands = [
            BotCommand("start", "ꜱᴛᴀʀᴛ ᴛʜᴇ ʙᴏᴛ 🚀"),

            # 🔗 Channel & Link Management
            BotCommand("addch", "ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ (ᴀᴅᴍɪɴ) ➕"),
            BotCommand("delch", "ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ (ᴀᴅᴍɪɴ) ➖"),
            BotCommand("channels", "ᴠɪᴇᴡ ᴀʟʟ ᴄʜᴀɴɴᴇʟꜱ 📋"),
            BotCommand("reqlink", "ᴠɪᴇᴡ ʀᴇQᴜᴇꜱᴛ ʟɪɴᴋꜱ 🔄"),
            BotCommand("links", "ɢᴇᴛ ᴀʟʟ ʟɪɴᴋꜱ 🔗"),
            BotCommand("bulklink", "ɢᴇɴᴇʀᴀᴛᴇ ʙᴜʟᴋ ʟɪɴᴋꜱ 📦"),
            BotCommand("reqtime", "ꜱᴇᴛ ᴀᴘᴘʀᴏᴠᴇ ᴛɪᴍᴇ ⏱️"),
            BotCommand("reqmode", "ᴛᴏɢɢʟᴇ ʀᴇQᴜᴇꜱᴛ ᴍᴏᴅᴇ ⚙️"),
            BotCommand("approveon", "ᴀᴜᴛᴏ ᴀᴘᴘʀᴏᴠᴇ ᴏɴ ✅"),
            BotCommand("approveoff", "ᴀᴜᴛᴏ ᴀᴘᴘʀᴏᴠᴇ ᴏꜰꜰ ❌"),
            BotCommand("approveall", "ᴀᴘᴘʀᴏᴠᴇ ᴀʟʟ ᴘᴇɴᴅɪɴɢ ✔️"),

            # 🔐 Admin Commands
            BotCommand("stats", "ʙᴏᴛ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ 📊"),
            BotCommand("status", "ʙᴏᴛ ꜱᴛᴀᴛᴜꜱ 🟢"),
            BotCommand("broadcast", "ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ 📢"),
            BotCommand("cleanup", "ᴄʟᴇᴀɴ ɪɴᴀᴄᴛɪᴠᴇ ᴜꜱᴇʀꜱ 🧹"),
        ]

        await self.set_bot_commands(commands)

        # 🔔 Notify Owner on Restart
        try:
            await self.send_message(
                chat_id=OWNER_ID,
                text="<b><blockquote>🤖 ʙᴏᴛ ʀᴇꜱᴛᴀʀᴛᴇᴅ ♻️</blockquote></b>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            self.LOGGER(__name__).warning(f"Failed to notify owner: {e}")

        self.set_parse_mode(ParseMode.HTML)
        self.LOGGER(__name__).info("Bot Running Successfully!")
        self.LOGGER(__name__).info(name)

        # 🌐 Web Server
        try:
            app = web.AppRunner(await web_server())
            await app.setup()
            bind_address = "0.0.0.0"
            await web.TCPSite(app, bind_address, PORT).start()
            self.LOGGER(__name__).info(f"Web server started on {bind_address}:{PORT}")
        except Exception as e:
            self.LOGGER(__name__).error(f"Web server failed: {e}")

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info("Bot stopped.")

# 🔄 Global Cancel Flag
is_canceled = False
cancel_lock = asyncio.Lock()

if __name__ == "__main__":
    Bot().run()
