import asyncio
import base64
import time
from asyncio import Lock
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ChatMemberStatus, ChatAction
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from pyrogram.errors import FloodWait, UserNotParticipant, UserIsBlocked, InputUserDeactivated
import os
import asyncio
from asyncio import sleep
from asyncio import Lock
import random 

from bot import Bot
from datetime import datetime, timedelta
from config import *
from database.database import *
from plugins.newpost import revoke_invite_after_5_minutes
from helper_func import *

# Create a lock dictionary for each channel to prevent concurrent link generation
channel_locks = defaultdict(asyncio.Lock)

user_banned_until = {}

# Broadcast variables
cancel_lock = asyncio.Lock()
is_canceled = False

# Random image selector for start
START_IMAGES = [
    "https://i.postimg.cc/02hcmLx7/3726acbf3c8d079d88edc7a54e22b1e6.jpg",
    "https://i.postimg.cc/Hsr6rpGy/3ff1f31ba3961d8111817de48aa47670.jpg",
    "https://i.postimg.cc/jdDMDsVP/56932388f91573455119ec6aa27e7cd9.jpg",
    "https://i.postimg.cc/dth5hqMR/c84af4f21fa1c3f4f2e1a056241e430d.jpg",
    "https://i.postimg.cc/rFDfD86V/df23ccf92c7fad0e0d59c1b316e559c9.jpg",
    "https://i.postimg.cc/L6JxJHdP/f881453d3689d3965023c7079a61a9b0.jpg"
]

@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Bot, message: Message):
    user_id = message.from_user.id

    if user_id in user_banned_until:
        if datetime.now() < user_banned_until[user_id]:
            return await message.reply_text(
                "<b><blockquote expandable>⚠️ ʏᴏᴜ ᴀʀᴇ ᴛᴇᴍᴘᴏʀᴀʀɪʟʏ ʙᴀɴɴᴇᴅ ғʀᴏᴍ ᴜsɪɴɢ ᴄᴏᴍᴍᴀɴᴅs ᴅᴜᴇ ᴛᴏ sᴘᴀᴍᴍɪɴɢ. ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.</b>",
                parse_mode=ParseMode.HTML
            )
            
    await add_user(user_id)

    text = message.text
    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]
            is_request = base64_string.startswith("req_")
            
            if is_request:
                base64_string = base64_string[4:]
                channel_id = await get_channel_by_encoded_link2(base64_string)
            else:
                channel_id = await get_channel_by_encoded_link(base64_string)
            
            if not channel_id:
                return await message.reply_text(
                    "<b><blockquote expandable>❌ ɪɴᴠᴀʟɪᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ ɪɴᴠɪᴛᴇ ʟɪɴᴋ.</b>",
                    parse_mode=ParseMode.HTML
                )

            # Check if this is a /genlink link (original_link exists)
            from database.database import get_original_link
            original_link = await get_original_link(channel_id)
            if original_link:
                button = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("• ᴘʀᴏᴄᴇᴇᴅ ᴛᴏ ʟɪɴᴋ •", url=original_link)]]
                )
                return await message.reply_text(
                    "<b><blockquote expandable>✨ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ! ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ ✨</b>",
                    reply_markup=button,
                    parse_mode=ParseMode.HTML
                )

            # Use a lock for this channel to prevent concurrent link generation
            async with channel_locks[channel_id]:
                # Check if we already have a valid link
                old_link_info = await get_current_invite_link(channel_id)
                current_time = datetime.now()
                
                # If we have an existing link and it's not expired yet (assuming 5 minutes validity)
                if old_link_info:
                    link_created_time = await get_link_creation_time(channel_id)
                    if link_created_time and (current_time - link_created_time).total_seconds() < 240:  # 4 minutes
                        # Use existing link
                        invite_link = old_link_info["invite_link"]
                        is_request_link = old_link_info["is_request"]
                    else:
                        # Revoke old link and create new one
                        try:
                            await client.revoke_chat_invite_link(channel_id, old_link_info["invite_link"])
                            print(f"Revoked old {'request' if old_link_info['is_request'] else 'invite'} link for channel {channel_id}")
                        except Exception as e:
                            print(f"Failed to revoke old link for channel {channel_id}: {e}")
                        
                        # Create new link
                        invite = await client.create_chat_invite_link(
                            chat_id=channel_id,
                            expire_date=current_time + timedelta(minutes=10),
                            creates_join_request=is_request
                        )
                        invite_link = invite.invite_link
                        is_request_link = is_request
                        await save_invite_link(channel_id, invite_link, is_request_link)
                else:
                    # Create new link
                    invite = await client.create_chat_invite_link(
                        chat_id=channel_id,
                        expire_date=current_time + timedelta(minutes=10),
                        creates_join_request=is_request
                    )
                    invite_link = invite.invite_link
                    is_request_link = is_request
                    await save_invite_link(channel_id, invite_link, is_request_link)

            button_text = "• ʀᴇǫᴜᴇsᴛ ᴛᴏ ᴊᴏɪɴ •" if is_request_link else "• ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ •"
            button = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=invite_link)]])

            wait_msg = await message.reply_text(
                "⏳",
                parse_mode=ParseMode.HTML
            )
            
            await wait_msg.delete()
            
            await message.reply_text(
                "<b><blockquote expandable>✨ ʜᴇʀᴇ ɪs ʏᴏᴜʀ ʟɪɴᴋ! ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ ✨</b>",
                reply_markup=button,
                parse_mode=ParseMode.HTML
            )

            note_msg = await message.reply_text(
                "<b><i>📌 ɴᴏᴛᴇ: ɪғ ᴛʜᴇ ʟɪɴᴋ ɪs ᴇxᴘɪʀᴇᴅ, ᴘʟᴇᴀsᴇ ᴄʟɪᴄᴋ ᴛʜᴇ ᴘᴏsᴛ ʟɪɴᴋ ᴀɢᴀɪɴ ᴛᴏ ɢᴇᴛ ᴀ ɴᴇᴡ ᴏɴᴇ.</i></b>",
                parse_mode=ParseMode.HTML
            )

            # Auto-delete the note message after 5 minutes
            asyncio.create_task(delete_after_delay(note_msg, 300))

            asyncio.create_task(revoke_invite_after_5_minutes(client, channel_id, invite_link, is_request_link))

        except Exception as e:
            await message.reply_text(
                "<b><blockquote expandable>❌ ɪɴᴠᴀʟɪᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ ɪɴᴠɪᴛᴇ ʟɪɴᴋ.</b>",
                parse_mode=ParseMode.HTML
            )
            print(f"Decoding error: {e}")
    else:
        # Random image selection
        start_image = random.choice(START_IMAGES)
        
        # Custom inline buttons with your anime channels - NO EMOJIS, just dots
        inline_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("• ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI1NDcyOTQzMzE")],
                [InlineKeyboardButton("• ʜᴇɴᴛᴀɪ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI5MDgyNDA3NDI")],
                [
                    InlineKeyboardButton("• ᴀʙᴏᴜᴛ •", callback_data="about"),
                    InlineKeyboardButton("• ᴄʜᴀɴɴᴇʟ •", url="https://t.me/DragonByte_Network")
                ],
                [InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data="close")]
            ]
        )
        
        # Cool start message with better UI
        START_MSG = f"""
╭━━━━━━━━━━━━━━━━━━╮
┃   ✨ ʏᴜᴛᴀ ꜱʜᴀʀᴇ ʙᴏᴛ ✨
╰━━━━━━━━━━━━━━━━━━╯

ʜᴇʏ {message.from_user.first_name},

ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ᴜʟᴛɪᴍᴀᴛᴇ ᴀɴɪᴍᴇ sʜᴀʀɪɴɢ ᴇxᴘᴇʀɪᴇɴᴄᴇ.

» ʏᴏᴜ ᴄᴀɴ ᴀᴄᴄᴇss ᴛᴡᴏ ᴇxᴄʟᴜsɪᴠᴇ ᴄʜᴀɴɴᴇʟs:
  • ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ
  • ʜᴇɴᴛᴀɪ ᴄʜᴀɴɴᴇʟ

» ᴜsᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ ʏᴏᴜʀ ᴘʀᴇғᴇʀʀᴇᴅ ᴄʜᴀɴɴᴇʟ.

──────────────────
ᴘᴏᴡᴇʀᴇᴅ ʙʏ @xFlexyy
ᴄᴏᴍᴍᴜɴɪᴛʏ @DragonByte_Network
──────────────────"""
        
        # Show waiting emoji and instantly delete it
        wait_msg = await message.reply_text("⏳")
        await asyncio.sleep(0.1)
        await wait_msg.delete()
        
        try:
            await message.reply_photo(
                photo=start_image,
                caption=START_MSG,
                reply_markup=inline_buttons,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Error sending start picture: {e}")
            await message.reply_text(
                START_MSG,
                reply_markup=inline_buttons,
                parse_mode=ParseMode.HTML
            )


#=====================================================================================##
# Bot by @xFlexyy | Community @DragonByte_Network

async def get_link_creation_time(channel_id):
    """Get the creation time of the current invite link for a channel."""
    try:
        from database.database import channels_collection
        channel = await channels_collection.find_one({"channel_id": channel_id, "status": "active"})
        if channel and "invite_link_created_at" in channel:
            return channel["invite_link_created_at"]
        return None
    except Exception as e:
        print(f"Error fetching link creation time for channel {channel_id}: {e}")
        return None

# Create a global dictionary to store chat data
chat_data_cache = {}

@Bot.on_callback_query(filters.regex("close"))
async def close_callback(client: Bot, callback_query):
    await callback_query.answer()
    await callback_query.message.delete()

@Bot.on_callback_query(filters.regex("check_sub"))
async def check_sub_callback(client: Bot, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    fsub_channels = await get_fsub_channels()
    
    if not fsub_channels:
        await callback_query.message.edit_text(
            "<b>ɴᴏ ғsᴜʙ ᴄʜᴀɴɴᴇʟs ᴄᴏɴғɪɢᴜʀᴇᴅ!</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    is_subscribed, subscription_message, subscription_buttons = await check_subscription_status(client, user_id, fsub_channels)
    if is_subscribed:
        await callback_query.message.edit_text(
            "<b>ʏᴏᴜ ᴀʀᴇ sᴜʙsᴄʀɪʙᴇᴅ ᴛᴏ ᴀʟʟ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs! ᴜsᴇ /start ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ.</b>",
            parse_mode=ParseMode.HTML
        )
    else:
        await callback_query.message.edit_text(
            subscription_message,
            reply_markup=subscription_buttons,
            parse_mode=ParseMode.HTML
        )

WAIT_MSG = "<b>⏳ ᴘʀᴏᴄᴇssɪɴɢ...</b>"

REPLY_ERROR = """ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴀs ᴀ ʀᴇᴘʟʏ ᴛᴏ ᴀɴʏ ᴛᴇʟᴇɢʀᴀᴍ ᴍᴇssᴀɢᴇ ᴡɪᴛʜᴏᴜᴛ ᴀɴʏ sᴘᴀᴄᴇs."""
# Define a global variable to store the cancel state
is_canceled = False
cancel_lock = Lock()

@Bot.on_message(filters.command('status') & filters.private & is_owner_or_admin)
async def info(client: Bot, message: Message):   
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data="close")]])
    
    start_time = time.time()
    temp_msg = await message.reply("<b>⏳ ᴘʀᴏᴄᴇssɪɴɢ...</b>", quote=True, parse_mode=ParseMode.HTML)
    end_time = time.time()
    
    ping_time = (end_time - start_time) * 1000
    
    users = await full_userbase()
    now = datetime.now()
    delta = now - client.uptime
    bottime = get_readable_time(delta.seconds)
    
    await temp_msg.edit(
        f"╭━━━━━━━━━━━━━━╮\n"
        f"┃   ʙᴏᴛ sᴛᴀᴛᴜs   ┃\n"
        f"╰━━━━━━━━━━━━━━╯\n\n"
        f"• ᴜsᴇʀs: <code>{len(users)}</code>\n"
        f"• ᴜᴘᴛɪᴍᴇ: <code>{bottime}</code>\n"
        f"• ᴘɪɴɢ: <code>{ping_time:.2f} ᴍs</code>\n\n"
        f"──────────────────\n"
        f"ᴘᴏᴡᴇʀᴇᴅ ʙʏ @xFlexyy\n"
        f"──────────────────",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

#--------------------------------------------------------------[[ADMIN COMMANDS]]---------------------------------------------------------------------------#
# Handler for the /cancel command
@Bot.on_message(filters.command('cancel') & filters.private & is_owner_or_admin)
async def cancel_broadcast(client: Bot, message: Message):
    global is_canceled
    async with cancel_lock:
        is_canceled = True
    await message.reply_text("<b>✅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ!</b>")

@Bot.on_message(filters.private & filters.command('broadcast') & is_owner_or_admin)
async def broadcast(client: Bot, message: Message):
    global is_canceled
    args = message.text.split()[1:]

    if not message.reply_to_message:
        msg = await message.reply(
            "<b>📢 ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ.</b>\n\n"
            "<b>ᴜsᴀɢᴇ ᴇxᴀᴍᴘʟᴇs:</b>\n"
            "<code>/broadcast normal</code>\n"
            "<code>/broadcast pin</code>\n"
            "<code>/broadcast delete 30</code>\n"
            "<code>/broadcast pin delete 30</code>\n"
            "<code>/broadcast silent</code>\n"
        )
        await asyncio.sleep(8)
        return await msg.delete()

    # Defaults
    do_pin = False
    do_delete = False
    duration = 0
    silent = False
    mode_text = []

    i = 0
    while i < len(args):
        arg = args[i].lower()
        if arg == "pin":
            do_pin = True
            mode_text.append("ᴘɪɴ")
        elif arg == "delete":
            do_delete = True
            try:
                duration = int(args[i + 1])
                i += 1
            except (IndexError, ValueError):
                return await message.reply("<b>❌ ᴘʀᴏᴠɪᴅᴇ ᴠᴀʟɪᴅ ᴅᴜʀᴀᴛɪᴏɴ ғᴏʀ ᴅᴇʟᴇᴛᴇ ᴍᴏᴅᴇ.</b>\nᴜsᴀɢᴇ: <code>/broadcast delete 30</code>")
            mode_text.append(f"ᴅᴇʟᴇᴛᴇ({duration}s)")
        elif arg == "silent":
            silent = True
            mode_text.append("sɪʟᴇɴᴛ")
        else:
            mode_text.append(arg.upper())
        i += 1

    if not mode_text:
        mode_text.append("ɴᴏʀᴍᴀʟ")

    # Reset cancel flag
    async with cancel_lock:
        is_canceled = False

    query = await full_userbase()
    broadcast_msg = message.reply_to_message
    total = len(query)
    successful = blocked = deleted = unsuccessful = 0

    pls_wait = await message.reply(f"<b>📢 ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ɪɴ <i>{' + '.join(mode_text)}</i> ᴍᴏᴅᴇ...</b>")

    bar_length = 20
    progress_bar = ''
    last_update_percentage = 0
    update_interval = 0.05  # 5%

    for i, chat_id in enumerate(query, start=1):
        async with cancel_lock:
            if is_canceled:
                await pls_wait.edit(f"<b>❌ ʙʀᴏᴀᴅᴄᴀsᴛ ({' + '.join(mode_text)}) ᴄᴀɴᴄᴇʟʟᴇᴅ</b>")
                return

        try:
            sent_msg = await broadcast_msg.copy(chat_id, disable_notification=silent)

            if do_pin:
                await client.pin_chat_message(chat_id, sent_msg.id, both_sides=True)
            if do_delete:
                asyncio.create_task(auto_delete(sent_msg, duration))

            successful += 1
        except FloodWait as e:
            await asyncio.sleep(e.x)
            try:
                sent_msg = await broadcast_msg.copy(chat_id, disable_notification=silent)
                if do_pin:
                    await client.pin_chat_message(chat_id, sent_msg.id, both_sides=True)
                if do_delete:
                    asyncio.create_task(auto_delete(sent_msg, duration))
                successful += 1
            except:
                unsuccessful += 1
        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1
        except InputUserDeactivated:
            await del_user(chat_id)
            deleted += 1
        except:
            unsuccessful += 1
            await del_user(chat_id)

        # Progress
        percent_complete = i / total
        if percent_complete - last_update_percentage >= update_interval or last_update_percentage == 0:
            num_blocks = int(percent_complete * bar_length)
            progress_bar = "█" * num_blocks + "░" * (bar_length - num_blocks)
            status_update = f"""<b>📢 ʙʀᴏᴀᴅᴄᴀsᴛ ({' + '.join(mode_text)})</b>

<code>[{progress_bar}] {percent_complete:.0%}</code>

<b>📊 sᴛᴀᴛɪsᴛɪᴄs:</b>
├ ᴛᴏᴛᴀʟ: <code>{total}</code>
├ sᴜᴄᴄᴇssғᴜʟ: <code>{successful}</code>
├ ʙʟᴏᴄᴋᴇᴅ: <code>{blocked}</code>
├ ᴅᴇʟᴇᴛᴇᴅ: <code>{deleted}</code>
└ ғᴀɪʟᴇᴅ: <code>{unsuccessful}</code>

<i>➪ ᴛᴏ sᴛᴏᴘ: <b>/cancel</b></i>"""
            await pls_wait.edit(status_update)
            last_update_percentage = percent_complete

    # Final status
    final_status = f"""<b>✅ ʙʀᴏᴀᴅᴄᴀsᴛ ({' + '.join(mode_text)}) ᴄᴏᴍᴘʟᴇᴛᴇᴅ</b>

<code>[{progress_bar}] {percent_complete:.0%}</code>

<b>📊 ғɪɴᴀʟ sᴛᴀᴛɪsᴛɪᴄs:</b>
├ ᴛᴏᴛᴀʟ: <code>{total}</code>
├ sᴜᴄᴄᴇssғᴜʟ: <code>{successful}</code>
├ ʙʟᴏᴄᴋᴇᴅ: <code>{blocked}</code>
├ ᴅᴇʟᴇᴛᴇᴅ: <code>{deleted}</code>
└ ғᴀɪʟᴇᴅ: <code>{unsuccessful}</code>

──────────────────
ᴘᴏᴡᴇʀᴇᴅ ʙʏ @xFlexyy
──────────────────"""
    return await pls_wait.edit(final_status)


# helper for delete mode
async def auto_delete(sent_msg, duration):
    await asyncio.sleep(duration)
    try:
        await sent_msg.delete()
    except:
        pass


#----------------------------------

user_message_count = {}
user_banned_until = {}

MAX_MESSAGES = 3
TIME_WINDOW = timedelta(seconds=10)
BAN_DURATION = timedelta(hours=1)

@Bot.on_callback_query()
async def cb_handler(client: Bot, query: CallbackQuery):
    data = query.data  
    chat_id = query.message.chat.id
    
    if data == "close":
        await query.message.delete()
        try:
            await query.message.reply_to_message.delete()
        except:
            pass
    
    elif data == "about":
        # Random image for about
        about_image = random.choice(START_IMAGES)
        
        ABOUT_TXT = f"""
╭━━━━━━━━━━━━━━━━━━╮
┃   ℹ️ ᴀʙᴏᴜᴛ ʙᴏᴛ   ┃
╰━━━━━━━━━━━━━━━━━━╯

• ʙᴏᴛ ɴᴀᴍᴇ: ʏᴜᴛᴀ sʜᴀʀᴇ ʙᴏᴛ
• ᴅᴇᴠᴇʟᴏᴘᴇʀ: @xFlexyy
• ᴄᴏᴍᴍᴜɴɪᴛʏ: @DragonByte_Network

ғᴇᴀᴛᴜʀᴇs:
» ᴇxᴄʟᴜsɪᴠᴇ ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ
» ʜᴇɴᴛᴀɪ ᴄᴏɴᴛᴇɴᴛ ᴀᴄᴄᴇss
» ғᴀsᴛ & ʀᴇʟɪᴀʙʟᴇ sʜᴀʀɪɴɢ
» 24/7 ᴜᴘᴛɪᴍᴇ

──────────────────
ᴘᴏᴡᴇʀᴇᴅ ʙʏ @xFlexyy
──────────────────"""
        
        await query.edit_message_media(
            InputMediaPhoto(
                about_image,
                ABOUT_TXT
            ),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton('• ʙᴀᴄᴋ •', callback_data='start'), 
                    InlineKeyboardButton('• ᴄʟᴏsᴇ •', callback_data='close')
                ]
            ]),
        )

    elif data == "channels":
        # Show anime channels directly
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("• ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI1NDcyOTQzMzE")],
            [InlineKeyboardButton("• ʜᴇɴᴛᴀɪ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI5MDgyNDA3NDI")],
            [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="start")]
        ])
        
        await query.message.edit_text(
            "<b>📢 sᴇʟᴇᴄᴛ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ:</b>",
            reply_markup=buttons,
            parse_mode=ParseMode.HTML
        )
        
    elif data in ["start", "home"]:
        # Random image selection
        start_image = random.choice(START_IMAGES)
        
        # Custom inline buttons with your anime channels - NO EMOJIS
        inline_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("• ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI1NDcyOTQzMzE")],
                [InlineKeyboardButton("• ʜᴇɴᴛᴀɪ ᴄʜᴀɴɴᴇʟ •", url="https://t.me/YutaShareBot?start=req_LTEwMDI5MDgyNDA3NDI")],
                [
                    InlineKeyboardButton("• ᴀʙᴏᴜᴛ •", callback_data="about"),
                    InlineKeyboardButton("• ᴄʜᴀɴɴᴇʟ •", url="https://t.me/DragonByte_Network")
                ],
                [InlineKeyboardButton("• ᴄʟᴏsᴇ •", callback_data="close")]
            ]
        )
        
        # Cool start message with better UI
        START_MSG = f"""
╭━━━━━━━━━━━━━━━━━━╮
┃   ✨ ʏᴜᴛᴀ ꜱʜᴀʀᴇ ʙᴏᴛ ✨
╰━━━━━━━━━━━━━━━━━━╯

ʜᴇʏ {query.from_user.first_name},

ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ᴜʟᴛɪᴍᴀᴛᴇ ᴀɴɪᴍᴇ sʜᴀʀɪɴɢ ᴇxᴘᴇʀɪᴇɴᴄᴇ.

» ʏᴏᴜ ᴄᴀɴ ᴀᴄᴄᴇss ᴛᴡᴏ ᴇxᴄʟᴜsɪᴠᴇ ᴄʜᴀɴɴᴇʟs:
  • ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ
  • ʜᴇɴᴛᴀɪ ᴄʜᴀɴɴᴇʟ

» ᴜsᴇ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴊᴏɪɴ ʏᴏᴜʀ ᴘʀᴇғᴇʀʀᴇᴅ ᴄʜᴀɴɴᴇʟ.

──────────────────
ᴘᴏᴡᴇʀᴇᴅ ʙʏ @xFlexyy
ᴄᴏᴍᴍᴜɴɪᴛʏ @DragonByte_Network
──────────────────"""
        
        try:
            await query.edit_message_media(
                InputMediaPhoto(
                    start_image,
                    START_MSG
                ),
                reply_markup=inline_buttons
            )
        except Exception as e:
            print(f"Error sending start/home photo: {e}")
            await query.edit_message_text(
                START_MSG,
                reply_markup=inline_buttons,
                parse_mode=ParseMode.HTML
            )


    elif data.startswith("rfs_ch_"):
        cid = int(data.split("_")[2])
        try:
            chat = await client.get_chat(cid)
            mode = await db.get_channel_mode(cid)
            status = "ᴏɴ" if mode == "on" else "ᴏғғ"
            new_mode = "ᴏғғ" if mode == "on" else "ᴏɴ"
            buttons = [
                [InlineKeyboardButton(f"ʀᴇǫ ᴍᴏᴅᴇ: {'ᴏғғ' if mode == 'on' else 'ᴏɴ'}", callback_data=f"rfs_toggle_{cid}_{new_mode}")],
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="fsub_back")]
            ]
            await query.message.edit_text(
                f"ᴄʜᴀɴɴᴇʟ: {chat.title}\nᴄᴜʀʀᴇɴᴛ ғᴏʀᴄᴇ-sᴜʙ ᴍᴏᴅᴇ: {status}",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception:
            await query.answer("ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ ᴄʜᴀɴɴᴇʟ ɪɴғᴏ", show_alert=True)

    elif data.startswith("rfs_toggle_"):
        cid, action = data.split("_")[2:]
        cid = int(cid)
        mode = "on" if action == "on" else "off"

        await db.set_channel_mode(cid, mode)
        await query.answer(f"ғᴏʀᴄᴇ-sᴜʙ sᴇᴛ ᴛᴏ {'ᴏɴ' if mode == 'on' else 'ᴏғғ'}")

        # Refresh the same channel's mode view
        chat = await client.get_chat(cid)
        status = "ᴏɴ" if mode == "on" else "ᴏғғ"
        new_mode = "ᴏғғ" if mode == "on" else "ᴏɴ"
        buttons = [
            [InlineKeyboardButton(f"ʀᴇǫ ᴍᴏᴅᴇ: {'ᴏғғ' if mode == 'on' else 'ᴏɴ'}", callback_data=f"rfs_toggle_{cid}_{new_mode}")],
            [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="fsub_back")]
        ]
        await query.message.edit_text(
            f"ᴄʜᴀɴɴᴇʟ: {chat.title}\nᴄᴜʀʀᴇɴᴛ ғᴏʀᴄᴇ-sᴜʙ ᴍᴏᴅᴇ: {status}",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data == "fsub_back":
        channels = await db.show_channels()
        buttons = []
        for cid in channels:
            try:
                chat = await client.get_chat(cid)
                mode = await db.get_channel_mode(cid)
                status = "🟢" if mode == "on" else "🔴"
                buttons.append([InlineKeyboardButton(f"{status} {chat.title}", callback_data=f"rfs_ch_{cid}")])
            except:
                continue

        await query.message.edit_text(
            "sᴇʟᴇᴄᴛ ᴀ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴛᴏɢɢʟᴇ ɪᴛs ғᴏʀᴄᴇ-sᴜʙ ᴍᴏᴅᴇ:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

def delete_after_delay(msg, delay):
    async def inner():
        await asyncio.sleep(delay)
        try:
            await msg.delete()
        except:
            pass
    return inner()
